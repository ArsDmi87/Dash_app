from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from dash import Dash
from dash.development.base_component import Component


@dataclass(frozen=True)
class ReportEntry:
    code: str
    name: str
    route: str
    layout: Callable[[], Component]
    register_callbacks: Callable[[Dash], None]
    permission_resource: Optional[str] = None
    description: Optional[str] = None


_REGISTRY: Dict[str, ReportEntry] = {}


def add_report(entry: ReportEntry) -> None:
    _REGISTRY[entry.route] = entry


def get_report(route: str) -> ReportEntry | None:
    return _REGISTRY.get(route)


def iter_reports() -> Iterable[ReportEntry]:
    return _REGISTRY.values()


def register_all_callbacks(app: Dash) -> None:
    for entry in _REGISTRY.values():
        entry.register_callbacks(app)
