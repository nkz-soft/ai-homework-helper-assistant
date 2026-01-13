from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

UI_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = UI_ROOT / "templates"
STATIC_DIR = UI_ROOT / "static"


def get_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_static_dir() -> Path:
    return STATIC_DIR
