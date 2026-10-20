"""View models: turn domain results into template-ready data.

Chart values travel as raw numbers for the axes, while every value a
human reads (tooltips, alternative tables) is formatted on the server
and passed in ``customdata``: JS never formats numbers (section 12.5).
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from backtesting_cripto.domain.models import BacktestResult, EquityPoint, Fill
from backtesting_cripto.web.formatters import (
    format_btc,
    format_date_es,
    format_eur,
    format_fng_label,
    format_reason_es,
    format_signed_eur,
    format_signed_pct,
)

OPERATIONS_PER_PAGE = 50


@dataclass(frozen=True)
class OperationRow:
    """One row of the operations table."""

    seq: int
    decision_day: date
    execution_day: date
    index_value: Decimal | None
    reason: str
    amount_eur: Decimal
    price_eur: Decimal
    btc_quantity: Decimal

    @property
    def differs_from_decision(self) -> bool:
        return self.execution_day != self.decision_day


def build_operation_rows(fills: Sequence[Fill]) -> list[OperationRow]:
    """Number the fills from 1 in execution order."""
    ordered = sorted(fills, key=lambda fill: (fill.execution_day, fill.decision_day))
    return [
        OperationRow(
            seq=index,
            decision_day=fill.decision_day,
            execution_day=fill.execution_day,
            index_value=fill.index_value,
            reason=fill.reason,
            amount_eur=fill.amount_eur,
            price_eur=fill.price_eur,
            btc_quantity=fill.btc_quantity,
        )
        for index, fill in enumerate(ordered, start=1)
    ]


def paginate_rows(
    rows: Sequence[OperationRow], page: int, per_page: int = OPERATIONS_PER_PAGE
) -> tuple[list[OperationRow], int, int]:
    """Return (page_rows, total_pages, safe_page)."""
    total = len(rows)
    total_pages = max(1, (total + per_page - 1) // per_page)
    safe_page = min(max(1, page), total_pages)
    start = (safe_page - 1) * per_page
    return list(rows[start : start + per_page]), total_pages, safe_page


def filter_rows_by_reason(
    rows: Sequence[OperationRow], reason: str | None
) -> list[OperationRow]:
    """Filter operation rows by rule (``None`` keeps all)."""
    if not reason or reason == "all":
        return list(rows)
    return [row for row in rows if row.reason == reason]


def _marker_size(amount_eur: Decimal) -> int:
    """Three discrete marker sizes proportional to the buy amount (§12.3)."""
    if amount_eur < Decimal("100"):
        return 8
    if amount_eur < Decimal("250"):
        return 12
    return 16


def _date_ticks(days: Sequence[date], count: int = 7) -> dict[str, object]:
    """Spanish date ticks generated on the server (§12.2).

    Plotly 3 has no ``registerLocale`` in the basic bundle, so the month
    names come from the server (``18 oct 2026``) as ``ticktext``.
    """
    if not days:
        return {}
    first, last = days[0], days[-1]
    if first == last:
        return {
            "tickmode": "array",
            "tickvals": [first.isoformat()],
            "ticktext": [format_date_es(first)],
        }

    span = (last - first).days
    step = max(1, span // (count - 1))
    values: list[str] = []
    labels: list[str] = []
    cursor = first
    while cursor < last:
        values.append(cursor.isoformat())
        labels.append(format_date_es(cursor))
        cursor += timedelta(days=step)
    values.append(last.isoformat())
    labels.append(format_date_es(last))
    return {"tickmode": "array", "tickvals": values, "ticktext": labels}


def _buy_markers(
    fills: Sequence[Fill], curve_by_day: Mapping[date, EquityPoint]
) -> tuple[list[str], list[float], list[int]]:
    """Days, portfolio values and marker sizes of the executed buys."""
    days: list[str] = []
    values: list[float] = []
    sizes: list[int] = []
    for fill in sorted(fills, key=lambda item: item.execution_day):
        point = curve_by_day.get(fill.execution_day)
        if point is None:
            continue
        days.append(fill.execution_day.isoformat())
        values.append(float(point.portfolio_value_eur))
        sizes.append(_marker_size(fill.amount_eur))
    return days, values, sizes


def build_g1_spec(result: BacktestResult) -> dict[str, object]:
    """G1: invested capital vs portfolio value, with buy markers."""
    curve = result.equity_curve
    curve_by_day = {point.day: point for point in curve}
    days = [point.day.isoformat() for point in curve]
    invested = [float(point.invested_eur) for point in curve]
    portfolio = [float(point.portfolio_value_eur) for point in curve]
    custom = [
        [
            format_date_es(point.day),
            format_eur(point.invested_eur),
            format_eur(point.portfolio_value_eur),
            format_signed_eur(point.portfolio_value_eur - point.invested_eur),
        ]
        for point in curve
    ]

    buy_days, buy_values, buy_sizes = _buy_markers(result.fills, curve_by_day)
    buy_custom = [
        [
            format_date_es(fill.execution_day),
            format_eur(fill.amount_eur),
            format_reason_es(fill.reason),
        ]
        for fill in sorted(result.fills, key=lambda item: item.execution_day)
        if fill.execution_day in curve_by_day
    ]

    return {
        "traces": [
            {
                "x": days,
                "y": invested,
                "name": "Capital invertido",
                "mode": "lines",
                "fill": "tozeroy",
                "line": {"width": 1.5},
                "meta": {"role": "invested"},
                "customdata": custom,
                "hovertemplate": (
                    "Día: %{customdata[0]}<br>"
                    "Invertido: %{customdata[1]}<br>"
                    "Valor: %{customdata[2]}<br>"
                    "Diferencia: %{customdata[3]}<extra></extra>"
                ),
            },
            {
                "x": days,
                "y": portfolio,
                "name": "Valor de la cartera",
                "mode": "lines",
                "line": {"width": 2},
                "meta": {"role": "portfolio"},
                "customdata": custom,
                "hovertemplate": (
                    "Día: %{customdata[0]}<br>"
                    "Valor: %{customdata[2]}<br>"
                    "Invertido: %{customdata[1]}<extra></extra>"
                ),
            },
            {
                "x": buy_days,
                "y": buy_values,
                "name": "Compras",
                "mode": "markers",
                "marker": {"symbol": "triangle-up", "size": buy_sizes},
                "meta": {"role": "buys"},
                "customdata": buy_custom,
                "hovertemplate": (
                    "Compra: %{customdata[1]}<br>Regla: %{customdata[2]}<br>"
                    "Día: %{customdata[0]}<extra></extra>"
                ),
            },
        ],
        "layout": {
            "yaxis": {"title": {"text": "Euros (€)"}},
            "xaxis": {"type": "date", **_date_ticks([point.day for point in curve])},
        },
        "config": {"scrollZoom": True},
    }


def build_g2_spec(
    result: BacktestResult, fng_values: Mapping[date, Decimal]
) -> dict[str, object]:
    """G2: Fear & Greed index line (violet) with buy markers (teal)."""
    index_days: list[str] = []
    index_values: list[float] = []
    index_custom: list[list[str]] = []
    index_day_dates = sorted(fng_values)
    for day in index_day_dates:
        value = fng_values[day]
        index_days.append(day.isoformat())
        index_values.append(float(value))
        index_custom.append([format_date_es(day), f"{int(value)}", format_fng_label(value)])

    fill_by_day = {fill.execution_day: fill for fill in result.fills}
    buy_days: list[str] = []
    buy_values: list[float] = []
    buy_sizes: list[int] = []
    buy_custom: list[list[str]] = []
    for day in sorted(fill_by_day):
        fill = fill_by_day[day]
        reading = fng_values.get(day)
        buy_days.append(day.isoformat())
        buy_values.append(float(reading) if reading is not None else 0.0)
        buy_sizes.append(_marker_size(fill.amount_eur))
        buy_custom.append(
            [
                format_date_es(day),
                f"{int(reading)}" if reading is not None else MISSING_TEXT,
                format_fng_label(reading),
                format_eur(fill.amount_eur),
                format_eur(fill.price_eur),
                format_btc(fill.btc_quantity),
            ]
        )

    return {
        "traces": [
            {
                "x": index_days,
                "y": index_values,
                "name": "Índice Fear & Greed",
                "mode": "lines",
                "connectgaps": False,
                "line": {"width": 1.5, "shape": "linear"},
                "meta": {"role": "fng"},
                "customdata": index_custom,
                "hovertemplate": (
                    "Día: %{customdata[0]}<br>"
                    "Índice: %{customdata[1]} (%{customdata[2]})<extra></extra>"
                ),
            },
            {
                "x": buy_days,
                "y": buy_values,
                "name": "Compras",
                "mode": "markers",
                "marker": {"symbol": "triangle-up", "size": buy_sizes},
                "meta": {"role": "buys"},
                "customdata": buy_custom,
                "hovertemplate": (
                    "Día: %{customdata[0]}<br>"
                    "Índice: %{customdata[1]} (%{customdata[2]})<br>"
                    "Compra: %{customdata[3]} a %{customdata[4]} → %{customdata[5]}<extra></extra>"
                ),
            },
        ],
        "layout": {
            "yaxis": {"title": {"text": "Índice (0–100)"}, "range": [-2, 102]},
            "xaxis": {"type": "date", **_date_ticks(index_day_dates)},
        },
        "config": {"scrollZoom": True},
    }


MISSING_TEXT = "—"


def build_g3_spec(result: BacktestResult) -> dict[str, object]:
    """G3: operations per index band (horizontal bars)."""
    counts = result.metrics.operations_by_reason
    ordered = sorted(counts.items(), key=lambda item: item[0])
    labels = [format_reason_es(reason) for reason, _ in ordered]
    values = [float(count) for _, count in ordered]
    return {
        "traces": [
            {
                "x": values,
                "y": labels,
                "name": "Operaciones",
                "type": "bar",
                "orientation": "h",
                "marker": {},
                "meta": {"role": "portfolio"},
                "customdata": [[count] for _, count in ordered],
                "texttemplate": "%{customdata[0]}",
                "textposition": "outside",
                "hovertemplate": "%{y}: %{customdata[0]} operaciones<extra></extra>",
            }
        ],
        "layout": {
            "xaxis": {"title": {"text": "Nº de operaciones"}, "dtick": 1},
            "yaxis": {"autorange": "reversed"},
            "showlegend": False,
        },
    }


def build_g4_spec(result: BacktestResult) -> dict[str, object]:
    """G4: drawdown curve (≤ 0)."""
    curve = result.equity_curve
    days = [point.day.isoformat() for point in curve]
    values = [float(point.drawdown_pct) for point in curve]
    custom = [
        [format_date_es(point.day), format_signed_pct(point.drawdown_pct)]
        for point in curve
    ]
    return {
        "traces": [
            {
                "x": days,
                "y": values,
                "name": "Drawdown",
                "mode": "lines",
                "fill": "tozeroy",
                "line": {"width": 1.5},
                "meta": {"role": "drawdown"},
                "customdata": custom,
                "hovertemplate": (
                    "Día: %{customdata[0]}<br>Drawdown: %{customdata[1]}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "yaxis": {"title": {"text": "Drawdown (%)"}, "ticksuffix": " %"},
            "xaxis": {"type": "date", **_date_ticks([point.day for point in curve])},
        },
    }


def build_chart_specs(
    result: BacktestResult, fng_values: Mapping[date, Decimal]
) -> dict[str, dict[str, object]]:
    """All chart specs, ready to be embedded as JSON."""
    return {
        "g1": build_g1_spec(result),
        "g2": build_g2_spec(result, fng_values),
        "g3": build_g3_spec(result),
        "g4": build_g4_spec(result),
    }


def chart_json(spec: Mapping[str, object]) -> str:
    """Serialize a chart spec for the ``data-chart-for`` script tag."""
    return json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
