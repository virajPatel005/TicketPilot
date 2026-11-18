#!/usr/bin/env python3
"""WCAG contrast check for both UI palettes (no network, no keys)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.theme import DARK, LIGHT  # noqa: E402


def _rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _lum(hex_color: str) -> float:
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colors."""
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


CHECKS = [
    ("body text on bg", "text", "bg", 7.0),
    ("body text on surface", "text", "surface", 7.0),
    ("muted on bg", "text_muted", "bg", 4.5),
    ("muted on surface", "text_muted", "surface", 4.5),
    ("button text on accent", "accent_text", "accent", 4.5),
    ("success badge", "success_text", "success_bg", 4.5),
    ("warning badge", "warning_text", "warning_bg", 4.5),
    ("info badge", "info_text", "info_bg", 4.5),
    ("danger badge", "danger_text", "danger_bg", 4.5),
    ("sidebar text on sidebar", "sidebar_text", "sidebar_bg", 7.0),
    ("nav muted on sidebar", "nav_muted", "sidebar_bg", 4.5),
    ("nav text on active bg", "sidebar_text", "nav_active_bg", 4.5),
    ("placeholder on input bg", "placeholder", "input_bg", 4.5),
    ("dropdown text on menu bg", "menu_text", "menu_bg", 4.5),
    ("selected option on hover", "menu_text", "menu_hover", 4.5),
]


def main() -> int:
    """Print the contrast table for both palettes. 0 if all pass."""
    failures = 0
    for name, palette in (("LIGHT", LIGHT), ("DARK", DARK)):
        print(f"== {name} ==")
        for label, fg_key, bg_key, minimum in CHECKS:
            value = ratio(palette[fg_key], palette[bg_key])
            ok = value >= minimum
            failures += 0 if ok else 1
            print(f"  {label:<28} {value:5.2f} (min {minimum}) "
                  f"{'PASS' if ok else 'FAIL'}")
    print("All pass." if not failures else f"{failures} FAILURES.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
