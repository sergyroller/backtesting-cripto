"""Unit tests for the Spanish Jinja2 formatters and design token rules."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting_cripto.web.formatters import (
    format_btc,
    format_date_es,
    format_eur,
    format_fng_label,
    format_pct,
    format_reason_es,
    format_signed_eur,
    format_signed_pct,
)
from backtesting_cripto.web.templating import create_jinja_environment

THIN_SPACE = "\u202f"
MINUS = "\u2212"
EN_DASH = "\u2013"


# --- EUR ----------------------------------------------------------------------


def test_format_eur_uses_spanish_separators() -> None:
    assert format_eur(Decimal("13300.00")) == f"13{THIN_SPACE}300,00\u2009€"
    assert format_eur(Decimal("80401.26")) == f"80{THIN_SPACE}401,26\u2009€"
    assert format_eur(Decimal("0.5")) == "0,50\u2009€"
    assert format_eur(None) == "\u2014"


def test_format_eur_negative_uses_typographic_minus() -> None:
    assert format_eur(Decimal("-380.00")) == f"{MINUS}380,00\u2009€"


def test_format_signed_eur_has_explicit_sign() -> None:
    assert format_signed_eur(Decimal("67101.26")) == f"+67{THIN_SPACE}101,26\u2009€"
    assert format_signed_eur(Decimal("-380.00")) == f"{MINUS}380,00\u2009€"
    assert format_signed_eur(Decimal("0.00")) == "0,00\u2009€"
    assert format_signed_eur(None) == "\u2014"


# --- Porcentajes --------------------------------------------------------------


def test_format_pct() -> None:
    assert format_pct(Decimal("504.52")) == "504,52\u2009%"
    assert format_pct(Decimal("-50.00")) == f"{MINUS}50,00\u2009%"
    assert format_pct(None) == "\u2014"


def test_format_signed_pct() -> None:
    assert format_signed_pct(Decimal("504.52")) == "+504,52\u2009%"
    assert format_signed_pct(Decimal("-50.00")) == f"{MINUS}50,00\u2009%"
    assert format_signed_pct(Decimal("0.00")) == "0,00\u2009%"


# --- BTC ----------------------------------------------------------------------


def test_format_btc_keeps_eight_decimals() -> None:
    assert format_btc(Decimal("1.10037310")) == "1,10037310 BTC"
    assert format_btc(Decimal("0.00136860")) == "0,00136860 BTC"
    assert format_btc(Decimal("0.000000019")) == "0,00000001 BTC"
    assert format_btc(None) == "\u2014"


# --- Fechas y razones ---------------------------------------------------------


def test_format_date_es_short_spanish() -> None:
    assert format_date_es(date(2026, 10, 18)) == "18 oct 2026"
    assert format_date_es(date(2018, 2, 1)) == "1 feb 2018"
    assert format_date_es(None) == "\u2014"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("daily_<10", "Diaria (< 10)"),
        ("monday_10_14", f"Lunes 10{EN_DASH}14"),
        ("monday_15_19", f"Lunes 15{EN_DASH}19"),
        ("monday_20_24", f"Lunes 20{EN_DASH}24"),
        ("unknown_rule", "unknown_rule"),
    ],
)
def test_format_reason_es(reason: str, expected: str) -> None:
    assert format_reason_es(reason) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("5"), "Miedo extremo"),
        (Decimal("30"), "Miedo"),
        (Decimal("60"), "Codicia"),
        (Decimal("90"), "Codicia extrema"),
        (None, "\u2014"),
    ],
)
def test_format_fng_label(value: Decimal | None, expected: str) -> None:
    assert format_fng_label(value) == expected


# --- Entorno Jinja2 -----------------------------------------------------------


def test_jinja_environment_registers_all_filters() -> None:
    environment = create_jinja_environment()
    for name in (
        "eur",
        "signed_eur",
        "pct",
        "signed_pct",
        "btc",
        "date_es",
        "date_es_long",
        "reason_es",
        "fng_label",
        "chart_json",
    ):
        assert name in environment.filters


def test_jinja_renders_filters() -> None:
    environment = create_jinja_environment()
    template = environment.from_string(
        "{{ amount | eur }}|{{ pnl | signed_eur }}|{{ btc | btc }}"
        "|{{ roi | signed_pct }}|{{ day | date_es }}|{{ reason | reason_es }}"
    )
    rendered = template.render(
        amount=Decimal("13300.00"),
        pnl=Decimal("67101.26"),
        btc=Decimal("1.10037310"),
        roi=Decimal("504.52"),
        day=date(2026, 10, 18),
        reason="monday_10_14",
    )
    assert rendered == (
        f"13{THIN_SPACE}300,00\u2009€"
        f"|+67{THIN_SPACE}101,26\u2009€"
        "|1,10037310 BTC"
        f"|+504,52\u2009%"
        "|18 oct 2026"
        f"|Lunes 10{EN_DASH}14"
    )


# --- Reglas de diseño ---------------------------------------------------------


def _css_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "src" / "backtesting_cripto" / "web" / "static" / "css"
    )


def _hex_values(css: str) -> list[str]:
    import re

    return re.findall(r"#[0-9a-fA-F]{3,8}\b", css)


def test_tokens_css_is_the_only_css_with_hex_colors() -> None:
    """Design rule: tokens.css is the single source of hex values."""
    css_dir = _css_dir()
    tokens = css_dir / "tokens.css"
    others = sorted(path for path in css_dir.glob("*.css") if path != tokens)

    assert _hex_values(tokens.read_text(encoding="utf-8"))
    for path in others:
        found = _hex_values(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} contains hex colors: {found[:5]}"


def test_tokens_css_defines_brand_and_dark_theme() -> None:
    css_dir = _css_dir()
    tokens = (css_dir / "tokens.css").read_text(encoding="utf-8")
    assert "--color-brand: #0DC3A4" in tokens
    assert '[data-theme="dark"]' in tokens
    assert "--color-negative: #CE2C31" in tokens
