from __future__ import annotations

from dash.development.base_component import Component, _explicitize_args


class DealDropdown(Component):
    """Custom dropdown component with project-specific styling."""

    _children_props: list[str] = []
    _base_nodes = ["children"]
    _namespace = "deal_dropdown"
    _type = "DealDropdown"

    @_explicitize_args
    def __init__(
        self,
        options=Component.UNDEFINED,
        value=Component.UNDEFINED,
        multi=Component.UNDEFINED,
        placeholder=Component.UNDEFINED,
        disabled=Component.UNDEFINED,
        searchable=Component.UNDEFINED,
        clearable=Component.UNDEFINED,
        style=Component.UNDEFINED,
        className=Component.UNDEFINED,
        id=Component.UNDEFINED,
        loading_state=Component.UNDEFINED,
        **kwargs,
    ):
        self._prop_names = [
            "options",
            "value",
            "multi",
            "placeholder",
            "disabled",
            "searchable",
            "clearable",
            "style",
            "className",
            "id",
            "loading_state",
        ]
        self._valid_wildcard_attributes: list[str] = []
        self.available_properties = self._prop_names.copy()
        self.available_wildcard_properties: list[str] = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)
        args = {k: _locals[k] for k in _explicit_args}

        super().__init__(**args)
