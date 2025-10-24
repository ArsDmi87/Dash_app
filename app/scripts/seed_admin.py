from __future__ import annotations

import argparse
import json
import sys
from typing import Mapping, Sequence

from app.admin import (
    AdminService,
    CreateRolePayload,
    CreateUserPayload,
    DuplicateRoleError,
    DuplicateUserError,
    RoleSummary,
    UserSummary,
)
from app.auth.service import AuthService
from app.core.settings import get_settings
from app.db.models import User
from app.db.session import get_auth_session_factory

DEFAULT_PERMISSIONS: Mapping[str, Sequence[str]] = {"admin": ("read", "write"), "*": ("read",)}


def _validate_password(password: str) -> None:
    if len(password.encode("utf-8")) > AuthService.MAX_PASSWORD_BYTES:
        raise ValueError(
            "Пароль слишком длинный для bcrypt (максимум 72 байта). "
            "Укоротите пароль или используйте меньше символов Unicode."
        )


def _find_role(service: AdminService, role_name: str) -> RoleSummary | None:
    roles = service.list_roles(include_inactive=True)
    return next((role for role in roles if role.role_name == role_name), None)


def _find_user(service: AdminService, username: str) -> UserSummary | None:
    users = service.list_users(include_inactive=True)
    return next((user for user in users if user.username == username), None)


def ensure_role(service: AdminService, role_name: str, description: str | None, permissions: Mapping[str, Sequence[str]]) -> RoleSummary:
    existing = _find_role(service, role_name)
    if existing:
        return existing

    payload = CreateRolePayload(
        role_name=role_name,
        description=description,
        permissions=permissions,
        is_active=True,
    )
    try:
        created = service.create_role(payload)
        print(f"[seed_admin] Создана роль '{created.role_name}' (id={created.role_id})")
        return created
    except DuplicateRoleError:
        # Параллельное создание: перечитываем
        existing = _find_role(service, role_name)
        if existing is None:
            raise RuntimeError("Не удалось получить роль после конфликтного создания")
        return existing


def ensure_user(
    service: AdminService,
    auth: AuthService,
    username: str,
    email: str,
    password: str,
    first_name: str | None,
    last_name: str | None,
    role_id: int,
) -> UserSummary:
    existing = _find_user(service, username)
    if existing:
        print(f"[seed_admin] Пользователь '{username}' уже существует (id={existing.user_id}), обновляем пароль")
        with service.session_factory() as session:  # type: ignore[attr-defined]
            user = session.get(User, existing.user_id)
            if user is None:
                raise RuntimeError("Пользователь исчез при повторном чтении")
            user.password_hash = auth.hash_password(password)
            user.is_active = True
            session.add(user)
            session.commit()
        return existing

    payload = CreateUserPayload(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        role_ids=[role_id],
    )
    try:
        created = service.create_user(payload)
        print(f"[seed_admin] Создан пользователь '{created.username}' (id={created.user_id})")
        return created
    except DuplicateUserError:
        # Повторная проверка: user мог появиться параллельно
        existing = _find_user(service, username)
        if existing is None:
            raise RuntimeError("Не удалось получить пользователя после конфликтного создания")
        print(f"[seed_admin] Пользователь '{username}' уже существует (id={existing.user_id}), пропускаем создание")
        return existing


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать администратора по умолчанию")
    parser.add_argument("--username", default="admin", help="Логин администратора (по умолчанию admin)")
    parser.add_argument("--email", default="admin@example.com", help="Email администратора")
    parser.add_argument("--password", required=True, help="Пароль администратора")
    parser.add_argument("--first-name", dest="first_name", default="Администратор", help="Имя администратора")
    parser.add_argument("--last-name", dest="last_name", default="Системы", help="Фамилия администратора")
    parser.add_argument("--role-name", dest="role_name", default="admin", help="Название роли администратора")
    parser.add_argument(
        "--role-description",
        dest="role_description",
        default="Администратор системы",
        help="Описание роли администратора",
    )
    parser.add_argument(
        "--permissions",
        default=json.dumps(DEFAULT_PERMISSIONS),
        help="JSON с правами роли администратора (по умолчанию {'admin': ['read','write'], '*': ['read']})",
    )
    parser.add_argument(
        "--report",
        dest="reports",
        action="append",
        default=[],
        help="Код отчёта (можно указать несколько флагов --report), который нужно назначить роли",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else None)

    try:
        permissions = json.loads(args.permissions)
        if not isinstance(permissions, dict):
            raise ValueError
        permissions_mapping: Mapping[str, Sequence[str]] = {
            resource: tuple(map(str, actions)) if isinstance(actions, (list, tuple, set)) else (str(actions),)
            for resource, actions in permissions.items()
        }
    except ValueError as exc:  # pragma: no cover - CLI защита
        print("[seed_admin] Некорректный формат параметра --permissions (ожидается JSON-объект)", file=sys.stderr)
        return 2

    try:
        _validate_password(args.password)
    except ValueError as exc:  # pragma: no cover - CLI защита
        print(f"[seed_admin] {exc}", file=sys.stderr)
        return 3

    settings = get_settings()
    session_factory = get_auth_session_factory(settings)
    service = AdminService(session_factory=session_factory, settings=settings)
    auth_service = AuthService(settings)

    role_summary = ensure_role(service, args.role_name, args.role_description, permissions_mapping)
    user_summary = ensure_user(
        service=service,
        auth=auth_service,
        username=args.username,
        email=args.email,
        password=args.password,
        first_name=args.first_name,
        last_name=args.last_name,
        role_id=role_summary.role_id,
    )

    if args.reports:
        available_reports = {report.report_code: report for report in service.list_reports(include_inactive=True)}
        missing_reports = []
        for raw_code in args.reports:
            code = (raw_code or "").strip()
            if not code:
                continue
            report = available_reports.get(code)
            if not report:
                missing_reports.append(code)
                continue
            service.assign_report_to_role(role_summary.role_id, report.report_id, can_view=True)
            print(f"[seed_admin] Назначен доступ роли '{role_summary.role_name}' к отчёту '{code}'")

        if missing_reports:
            print(
                f"[seed_admin] Предупреждение: отчёты с кодами {missing_reports} не найдены в базе и не были назначены",
                file=sys.stderr,
            )

    print("[seed_admin] Готово.")
    print(
        json.dumps(
            {
                "user_id": user_summary.user_id,
                "username": user_summary.username,
                "email": user_summary.email,
                "role_ids": user_summary.role_ids,
                "reports": args.reports,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
