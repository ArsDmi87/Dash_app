(function () {
  const React = window.React;
  const PropTypes = window.PropTypes;

  if (!React) {
    console.error("React is required for deal_dropdown.DealDropdown.");
    return;
  }

  const noop = () => {};

  const CONTROL_STYLES = {
    background:
      "linear-gradient(180deg, rgba(33, 22, 60, 0.92) 0%, rgba(13, 8, 26, 0.9) 100%)",
    border: "1px solid rgba(255, 255, 255, 0.4)",
    borderRadius: "12px",
    minHeight: "40px",
    padding: "4px 10px",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    cursor: "pointer",
    boxShadow: "none",
    color: "#FFFFFF",
    flexWrap: "wrap",
  };

  const TAG_STYLES = {
    backgroundColor: "rgba(74, 94, 174, 0.75)",
    color: "#FFFFFF",
    borderRadius: "10px",
    padding: "2px 10px",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    margin: "4px 6px 4px 0",
    fontSize: "13px",
  };

  const MENU_STYLES = {
    position: "absolute",
    left: 0,
    right: 0,
    top: "calc(100% + 6px)",
    zIndex: 1050,
    background:
      "linear-gradient(180deg, rgba(30, 18, 58, 0.95) 0%, rgba(12, 7, 24, 0.9) 100%)",
    borderRadius: "12px",
    border: "1px solid rgba(255, 255, 255, 0.18)",
    maxHeight: "260px",
    overflowY: "auto",
    boxShadow: "0 18px 36px rgba(0, 0, 0, 0.45)",
  };

  const OPTION_STYLES = {
    padding: "10px 16px",
    color: "#FFFFFF",
    cursor: "pointer",
  };

const OPTION_ACTIVE_STYLES = {
  backgroundColor: "rgba(74, 94, 174, 0.75)",
};

  const PLACEHOLDER_COLOR = "#FFFFFF";

  const getNormalizedOptions = (options) =>
    (options || []).map((opt) => {
      if (typeof opt === "string" || typeof opt === "number" || typeof opt === "boolean") {
        return { label: String(opt), value: opt };
      }
      if (opt && typeof opt === "object") {
        return {
          label:
            typeof opt.label === "string" || typeof opt.label === "number"
              ? String(opt.label)
              : opt.label,
          value: opt.value,
          disabled: Boolean(opt.disabled),
          raw: opt,
        };
      }
      return { label: "", value: opt };
    });

  const labelToString = (label, value) => {
    if (typeof label === "string" || typeof label === "number") {
      return String(label);
    }
    if (
      label &&
      typeof label === "object" &&
      "props" in label &&
      label.props &&
      label.props.children !== undefined
    ) {
      const child = label.props.children;
      if (typeof child === "string" || typeof child === "number") {
        return String(child);
      }
    }
    if (value !== undefined) {
      return String(value);
    }
    return "";
  };

  const DealDropdown = (props) => {
    const {
      id,
      options,
      value,
      multi,
      placeholder,
      disabled,
      searchable,
      clearable,
      className,
      style,
      setProps = noop,
    } = props;

    const normalized = React.useMemo(() => getNormalizedOptions(options), [options]);

    const [open, setOpen] = React.useState(false);
    const [searchTerm, setSearchTerm] = React.useState("");
    const containerRef = React.useRef(null);

    const selectedValues = React.useMemo(() => {
      if (multi) {
        return Array.isArray(value) ? value : [];
      }
      return value !== undefined && value !== null ? [value] : [];
    }, [value, multi]);

    const filteredOptions = React.useMemo(() => {
      const term = (searchTerm || "").toLowerCase();
      if (!term) {
        return normalized;
      }
      return normalized.filter((opt) => {
        const label = labelToString(opt.label, opt.value).toLowerCase();
        const search = opt.raw && typeof opt.raw.search === "string" ? opt.raw.search.toLowerCase() : label;
        return label.includes(term) || search.includes(term);
      });
    }, [normalized, searchTerm]);

    const isSelected = React.useCallback(
      (option) => selectedValues.some((val) => val === option.value),
      [selectedValues],
    );

    const closeOnOutside = React.useCallback(
      (event) => {
        if (!containerRef.current) {
          return;
        }
        if (!containerRef.current.contains(event.target)) {
          setOpen(false);
          setSearchTerm("");
        }
      },
      [containerRef],
    );

    React.useEffect(() => {
      if (open) {
        document.addEventListener("mousedown", closeOnOutside);
      } else {
        document.removeEventListener("mousedown", closeOnOutside);
      }
      return () => document.removeEventListener("mousedown", closeOnOutside);
    }, [open, closeOnOutside]);

    const handleSelect = (option) => {
      if (option.disabled) {
        return;
      }

      if (multi) {
        const exists = selectedValues.includes(option.value);
        const newValue = exists
          ? selectedValues.filter((item) => item !== option.value)
          : [...selectedValues, option.value];
        setProps({ value: newValue });
      } else {
        setProps({ value: option.value });
        setOpen(false);
      }
    };

    const handleClear = (event) => {
      event.stopPropagation();
      if (multi) {
        setProps({ value: [] });
      } else {
        setProps({ value: null });
      }
      setSearchTerm("");
    };

    const renderTags = () =>
      selectedValues
        .map((val) => normalized.find((opt) => opt.value === val))
        .filter(Boolean)
        .map((opt) =>
          React.createElement(
            "span",
            {
              key: String(opt.value),
              style: TAG_STYLES,
            },
            React.createElement("span", null, labelToString(opt.label, opt.value)),
            React.createElement(
              "button",
              {
                type: "button",
                onClick: (event) => {
                  event.stopPropagation();
                  handleSelect(opt);
                },
                style: {
                  background: "transparent",
                  border: "none",
                  color: "#FFFFFF",
                  cursor: "pointer",
                },
              },
              "×",
            ),
          ),
        );

    const selectedLabel = React.useMemo(() => {
      if (multi) {
        return null;
      }
      const opt = normalized.find((item) => item.value === selectedValues[0]);
      return opt ? labelToString(opt.label, opt.value) : null;
    }, [multi, selectedValues, normalized]);

    const arrow = React.createElement(
      "span",
      {
        style: {
          marginLeft: "auto",
          transition: "transform 0.2s ease",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
        },
      },
      "▾",
    );

    const showPlaceholderTag = multi && selectedValues.length === 0 && !searchTerm;

    const inputField =
      searchable !== false
        ? React.createElement("input", {
            type: "text",
            value: searchTerm,
            onChange: (event) => setSearchTerm(event.target.value),
            onClick: (event) => event.stopPropagation(),
            placeholder: showPlaceholderTag ? "" : placeholder || "",
            style: {
              flex: 1,
              minWidth: "120px",
              background: "transparent",
              border: "none",
              color: "#FFFFFF",
              outline: "none",
            },
            disabled,
          })
        : null;

    const classNames = ["deal-dropdown", className].filter(Boolean).join(" ");

    return React.createElement(
      "div",
      {
        id,
        className: classNames,
        ref: containerRef,
        style: Object.assign(
          {
            position: "relative",
            width: "100%",
            fontFamily: "inherit",
          },
          style || {},
        ),
      },
      React.createElement(
        "div",
        {
          role: "button",
          tabIndex: disabled ? -1 : 0,
          onClick: () => {
            if (disabled) {
              return;
            }
            setOpen((prev) => !prev);
          },
          onKeyDown: (event) => {
            if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
              event.preventDefault();
              if (!disabled) {
                setOpen((prev) => !prev);
              }
            } else if (event.key === "Escape") {
              setOpen(false);
            }
          },
          style: Object.assign({}, CONTROL_STYLES, disabled ? { opacity: 0.6, cursor: "not-allowed" } : {}),
        },
        showPlaceholderTag
          ? React.createElement(
              "span",
              {
                style: { color: PLACEHOLDER_COLOR, opacity: 0.7, marginRight: "auto" },
              },
              placeholder || "",
            )
          : null,
        multi ? renderTags() : selectedLabel
          ? React.createElement(
              "span",
              {
                style: { color: "#FFFFFF", marginRight: "auto" },
              },
              selectedLabel,
            )
          : React.createElement(
              "span",
              {
                style: { color: PLACEHOLDER_COLOR, opacity: 0.7, marginRight: "auto" },
              },
              placeholder || "",
            ),
        inputField,
        clearable !== false && (multi ? selectedValues.length > 0 : selectedLabel !== null)
          ? React.createElement(
              "button",
              {
                type: "button",
                onClick: handleClear,
                style: {
                  background: "transparent",
                  border: "none",
                  color: "#FFFFFF",
                  cursor: "pointer",
                  marginLeft: "4px",
                },
                disabled,
              },
              "×",
            )
          : null,
        arrow,
      ),
      open
        ? React.createElement(
            "div",
            { style: MENU_STYLES, id: `${id || ""}-menu` },
            filteredOptions.map((option, index) =>
              React.createElement(
                "div",
                {
                  key: `${String(option.value)}-${index}`,
                  onClick: (event) => {
                    event.stopPropagation();
                    handleSelect(option);
                  },
                  onMouseEnter: (event) => {
                    if (!isSelected(option)) {
                      event.currentTarget.style.backgroundColor = OPTION_ACTIVE_STYLES.backgroundColor;
                    }
                  },
                  onMouseLeave: (event) => {
                    if (!isSelected(option)) {
                      event.currentTarget.style.backgroundColor = OPTION_BG_COLOR;
                    }
                  },
                  style: Object.assign(
                    {},
                    OPTION_STYLES,
                    option.disabled ? { opacity: 0.5, cursor: "not-allowed" } : null,
                    isSelected(option)
                      ? { backgroundColor: "rgba(255, 255, 255, 0.08)", color: "#FFFFFF" }
                      : null,
                  ),
                },
                React.createElement(
                  "div",
                  null,
                  option.label !== undefined ? option.label : labelToString(option.label, option.value),
                ),
              ),
            ),
            filteredOptions.length === 0
              ? React.createElement(
                  "div",
                  {
                    style: Object.assign({}, OPTION_STYLES, { opacity: 0.6, cursor: "default" }),
                  },
                  "Нет значений",
                )
              : null,
          )
        : null,
    );
  };

  DealDropdown.defaultProps = {
    options: [],
    value: null,
    multi: true,
    placeholder: "",
    disabled: false,
    searchable: true,
    clearable: true,
  };

  DealDropdown.propTypes = {
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    options: PropTypes.arrayOf(
      PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.number,
        PropTypes.bool,
        PropTypes.shape({
          label: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
          value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool]),
          disabled: PropTypes.bool,
          title: PropTypes.string,
          search: PropTypes.string,
        }),
      ]),
    ),
    value: PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.number,
      PropTypes.bool,
      PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool])),
    ]),
    multi: PropTypes.bool,
    placeholder: PropTypes.string,
    disabled: PropTypes.bool,
    searchable: PropTypes.bool,
    clearable: PropTypes.bool,
    className: PropTypes.string,
    style: PropTypes.object,
    loading_state: PropTypes.shape({
      is_loading: PropTypes.bool,
      prop_name: PropTypes.string,
      component_name: PropTypes.string,
    }),
    setProps: PropTypes.func,
  };

  window.deal_dropdown = window.deal_dropdown || {};
  window.deal_dropdown.DealDropdown = DealDropdown;
})();
