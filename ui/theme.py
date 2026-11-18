"""TicketPilot UI theme palettes (enterprise). CSS variables are the source
of truth; Streamlit / browser defaults are never relied on for color."""

LIGHT = {
    "bg": "#F5F7FA",
    "surface": "#FFFFFF",
    "surface_2": "#EEF2F7",
    "border": "#D8E0EC",
    "text": "#1A2433",
    "text_muted": "#5B6B7F",
    "accent": "#0C5CAB",
    "accent_text": "#FFFFFF",
    "sidebar_bg": "#14213D",
    "sidebar_text": "#E8EEF7",
    "nav_hover": "#1D3055",
    "nav_active_bg": "#1E3A66",
    "nav_active_bar": "#4DA3FF",
    "nav_muted": "#A8B8D0",
    "divider": "#26385C",
    "success_bg": "#D1FAE5",
    "success_text": "#065F46",
    "warning_bg": "#FEF3C7",
    "warning_text": "#92400E",
    "info_bg": "#DBEAFE",
    "info_text": "#1D4ED8",
    "danger_bg": "#FEE2E2",
    "danger_text": "#991B1B",
    "input_bg": "#FFFFFF",
    "input_border": "#B9C6D8",
    "placeholder": "#5B6B7F",
    "menu_bg": "#FFFFFF",
    "menu_text": "#1A2433",
    "menu_hover": "#E8EEF7",
    "table_header_bg": "#E8EEF7",
}

DARK = {
    "bg": "#0F1623",
    "surface": "#182235",
    "surface_2": "#1F2C44",
    "border": "#33456B",
    "text": "#E6EDF7",
    "text_muted": "#9FB0C6",
    "accent": "#4DA3FF",
    "accent_text": "#0B1220",
    "sidebar_bg": "#0E1116",
    "sidebar_text": "#E6EDF7",
    "nav_hover": "#1A2230",
    "nav_active_bg": "#16283F",
    "nav_active_bar": "#4DA3FF",
    "nav_muted": "#8B98B0",
    "divider": "#232E40",
    "success_bg": "#064E3B",
    "success_text": "#A7F3D0",
    "warning_bg": "#78350F",
    "warning_text": "#FDE68A",
    "info_bg": "#1E3A8A",
    "info_text": "#BFDBFE",
    "danger_bg": "#7F1D1D",
    "danger_text": "#FECACA",
    "input_bg": "#101A2C",
    "input_border": "#3D5578",
    "placeholder": "#9FB0C6",
    "menu_bg": "#182235",
    "menu_text": "#E6EDF7",
    "menu_hover": "#1F2C44",
    "table_header_bg": "#1F2C44",
}

PALETTES = {"Light": LIGHT, "Dark": DARK}

# Status -> (background token, text token, label)
STATUS_STYLES = {
    "auto_resolved": ("success_bg", "success_text", "Auto-resolved"),
    "pending_approval": ("warning_bg", "warning_text", "Pending approval"),
    "approved": ("info_bg", "info_text", "Approved"),
    "rejected": ("danger_bg", "danger_text", "Rejected"),
}


def css_variables(palette: dict) -> str:
    """Render a palette dict as a :root CSS variable block."""
    lines = [":root {"]
    for key, value in palette.items():
        lines.append(f"  --{key.replace('_', '-')}: {value};")
    lines.append("}")
    return "\n".join(lines)
