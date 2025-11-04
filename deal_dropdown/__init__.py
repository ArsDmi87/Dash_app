from .component import DealDropdown

__all__ = ["DealDropdown", "__version__"]
__version__ = "0.1.0"

_js_dist = [
    {
        "relative_package_path": "deal_dropdown.js",
        "namespace": "deal_dropdown",
    }
]
_css_dist: list[dict] = []

DealDropdown._js_dist = _js_dist  # type: ignore[attr-defined]
DealDropdown._css_dist = _css_dist  # type: ignore[attr-defined]
