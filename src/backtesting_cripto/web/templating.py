"""Jinja2 environment with the Spanish formatters registered (§6.5)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backtesting_cripto.web.formatters import FILTERS

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_jinja_environment() -> Environment:
    """Build the Jinja2 environment used by the HTML views."""
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
        auto_reload=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters.update(FILTERS)
    return environment
