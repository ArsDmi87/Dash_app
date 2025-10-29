from __future__ import annotations

from .registry import ReportEntry, add_report, get_report, iter_reports, register_all_callbacks

# Import built-in reports so they register themselves on module import.
from . import sales_dashboard  # noqa: F401
from . import product_dynamics  # noqa: F401
from . import top_client_activities  # noqa: F401

__all__ = [
    "ReportEntry",
    "add_report",
    "get_report",
    "iter_reports",
    "register_all_callbacks",
]
