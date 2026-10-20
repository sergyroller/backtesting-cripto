"""Server-side Spanish formatters, registered as Jinja2 filters (section 6.5).

All money formatting happens here so HTMX fragments and the initial page
share the exact same format: EUR with 2 decimals and a thin-space
thousands separator, BTC with 8 decimals, explicit signs for deltas and
short Spanish dates.
"""

import json
from datetime import date
from decimal import Decimal

from backtesting_cripto.domain.models import quantize_btc, quantize_eur

THIN_SPACE = "\u202f"
MINUS_SIGN = "\u2212"
EN_DASH = "\u2013"
EM_DASH = "\u2014"
MISSING = EM_DASH

MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
MONTHS_ES_ABBR = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

# Qualitative labels of the Fear & Greed index (section 12.4).
FNG_LABELS: tuple[tuple[int, str], ...] = (
    (25, "Miedo extremo"),
    (50, "Miedo"),
    (75, "Codicia"),
    (101, "Codicia extrema"),
)


def group_thousands(integer_digits: str) -> str:
    """Group integer digits in threes with a thin space (U+202F)."""
    groups: list[str] = []
    while len(integer_digits) > 3:
        groups.insert(0, integer_digits[-3:])
        integer_digits = integer_digits[:-3]
    groups.insert(0, integer_digits)
    return THIN_SPACE.join(groups)


def format_decimal_es(value: Decimal, places: int) -> str:
    """Format a Decimal with Spanish separators and the given decimals."""
    quantized = Decimal(value).quantize(Decimal(1).scaleb(-places))
    sign = MINUS_SIGN if quantized < 0 else ""
    digits = f"{abs(quantized):.{places}f}"
    integer_part, _, decimal_part = digits.partition(".")
    return f"{sign}{group_thousands(integer_part)},{decimal_part}"


def format_eur(value: Decimal | None) -> str:
    """``13300.00`` -> ``13 300,00 €`` (``—`` when missing)."""
    if value is None:
        return MISSING
    return f"{format_decimal_es(quantize_eur(value), 2)}\u2009€"


def format_signed_eur(value: Decimal | None) -> str:
    """``+67 101,26 €`` / ``−380,00 €`` with an explicit sign."""
    if value is None:
        return MISSING
    quantized = quantize_eur(value)
    if quantized > 0:
        return f"+{format_decimal_es(quantized, 2)}\u2009€"
    if quantized < 0:
        return f"{MINUS_SIGN}{format_decimal_es(abs(quantized), 2)}\u2009€"
    return f"{format_decimal_es(quantized, 2)}\u2009€"


def format_pct(value: Decimal | None, places: int = 2) -> str:
    """``504.52`` -> ``504,52 %``."""
    if value is None:
        return MISSING
    return f"{format_decimal_es(value, places)}\u2009%"


def format_signed_pct(value: Decimal | None, places: int = 2) -> str:
    """``+504,52 %`` / ``−50,00 %`` with an explicit sign."""
    if value is None:
        return MISSING
    if value > 0:
        return f"+{format_decimal_es(value, places)}\u2009%"
    if value < 0:
        return f"{MINUS_SIGN}{format_decimal_es(abs(value), places)}\u2009%"
    return f"{format_decimal_es(value, places)}\u2009%"


def format_btc(value: Decimal | None) -> str:
    """``1.10037310`` -> ``1,10037310 BTC`` (8 decimals, ROUND_DOWN)."""
    if value is None:
        return MISSING
    quantized = quantize_btc(Decimal(value))
    return f"{format_decimal_es(quantized, 8)} BTC"


def format_date_es(value: date | None) -> str:
    """``date(2026, 10, 18)`` -> ``18 oct 2026``."""
    if value is None:
        return MISSING
    return f"{value.day} {MONTHS_ES_ABBR[value.month - 1]} {value.year}"


def format_date_es_long(value: date | None) -> str:
    """``18 octubre 2026`` (long form)."""
    if value is None:
        return MISSING
    return f"{value.day} de {MONTHS_ES[value.month - 1]} de {value.year}"


def format_reason_es(reason: str) -> str:
    """``daily_<10`` -> ``Diaria (< 10)``; ``monday_10_14`` -> ``Lunes 10–14``."""
    if reason.startswith("daily_<"):
        threshold = reason[len("daily_<") :]
        return f"Diaria (< {threshold})"
    if reason.startswith("monday_"):
        parts = reason[len("monday_") :].split("_")
        if len(parts) == 2:
            return f"Lunes {parts[0]}{EN_DASH}{parts[1]}"
    return reason


def format_fng_label(value: Decimal | int | None) -> str:
    """Qualitative label of a Fear & Greed reading (``—`` when missing)."""
    if value is None:
        return MISSING
    reading = int(value)
    for upper_bound, label in FNG_LABELS:
        if reading < upper_bound:
            return label
    return FNG_LABELS[-1][1]


def chart_json(spec: object) -> str:
    """Serialize a chart spec for the ``data-chart-for`` script tag."""
    return json.dumps(spec, ensure_ascii=False, separators=(",", ":"))


FILTERS: dict[str, object] = {
    "eur": format_eur,
    "signed_eur": format_signed_eur,
    "pct": format_pct,
    "signed_pct": format_signed_pct,
    "btc": format_btc,
    "date_es": format_date_es,
    "date_es_long": format_date_es_long,
    "reason_es": format_reason_es,
    "fng_label": format_fng_label,
    "chart_json": chart_json,
}
