"""Optional brand/theme CSS layer (Data/Branding/dashboard-theme.css)."""

from __future__ import annotations

from common.paths import THEME_CSS


def load_theme_css() -> str:
    if not THEME_CSS.exists():
        print(f"  NOTE: {THEME_CSS} not found; skipping theme CSS")
        return ""
    css = THEME_CSS.read_text(encoding="utf-8").strip()
    if css:
        print(f"  theme CSS: {THEME_CSS.name} ({len(css)} bytes)")
    return css
