"""HTML views (Simulador, Historial, Datos) rendered with Jinja2.

Every human-readable value is formatted on the server; HTMX swaps
replace fragments so the browser never formats numbers.
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from jinja2 import TemplateNotFound
from pydantic import ValidationError

from backtesting_cripto.domain.exceptions import (
    ConfigurationError,
    DataValidationError,
    DomainError,
    InsufficientDataError,
)
from backtesting_cripto.domain.models import BacktestConfig, BacktestResult
from backtesting_cripto.services.backtest_service import BacktestService
from backtesting_cripto.services.data_service import DataService
from backtesting_cripto.web.formatters import (
    format_eur,
    format_fng_label,
    format_signed_eur,
    format_signed_pct,
)
from backtesting_cripto.web.presenters import (
    build_chart_specs,
    build_operation_rows,
    filter_rows_by_reason,
    paginate_rows,
)
from backtesting_cripto.web.templating import create_jinja_environment

FNG_INDICATOR = "fear_greed"
ALT_SAMPLE = 10


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _parse_decimal(raw: str) -> Decimal:
    """Parse a Spanish-formatted amount (``50,00`` or ``50.00``)."""
    text = raw.strip().replace("\u202f", "").replace("\u2009", "").replace(",", ".")
    if not text:
        msg = "importe vacío"
        raise InvalidOperation(msg)
    return Decimal(text)


def _amount_to_form(value: object) -> str:
    """Render an amount for the form with a Spanish decimal comma."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "0,00"
    return f"{amount.quantize(Decimal('0.01')):.2f}".replace(".", ",")


def _spanish_errors(error: Exception) -> list[str]:
    """Turn a domain/validation error into specific Spanish messages."""
    if isinstance(error, ConfigurationError):
        message = str(error)
        if "overlap" in message.lower():
            return [
                "Hay tramos semanales solapados: ningún tramo puede compartir "
                "valores con otro."
            ]
        if "daily_below_threshold" in message or "threshold" in message.lower():
            return [
                "Los tramos semanales deben empezar en el umbral diario o por encima de él."
            ]
        if "window" in message.lower() or "outside" in message.lower():
            return [
                "El rango de fechas se sale de la cobertura disponible "
                "(revisa «Disponible» bajo los campos de fecha)."
            ]
        if "start_date" in message:
            return ["La fecha de inicio debe ser anterior o igual a la fecha de fin."]
        return [f"Configuración no válida: {message}"]
    if isinstance(error, InsufficientDataError):
        return [f"No hay datos suficientes: {error}"]
    if isinstance(error, DataValidationError):
        return [f"Los datos almacenados no pasan la validación: {error}"]
    if isinstance(error, DomainError):
        return [str(error)]
    if isinstance(error, ValidationError):
        return [
            "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in error.errors()
            )
        ]
    if isinstance(error, (InvalidOperation, ValueError)):
        return [f"Valor no válido: {error}"]
    return [f"Error inesperado: {error}"]


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Normalize Spanish decimal commas in incoming strategy parameters.

    The UI works in Spanish format (``50,00``); Pydantic needs ``50.00``.
    """
    normalized = dict(params)

    if "daily_amount_eur" in normalized:
        normalized["daily_amount_eur"] = str(
            _parse_decimal(str(normalized["daily_amount_eur"]))
        )

    bands = normalized.get("weekly_bands")
    if isinstance(bands, list):
        normalized["weekly_bands"] = [
            {
                **band,
                "amount_eur": str(_parse_decimal(str(band["amount_eur"]))),
            }
            if isinstance(band, dict) and "amount_eur" in band
            else band
            for band in bands
        ]
    return normalized


def create_web_router(
    *,
    data_service: DataService,
    backtest_service: BacktestService,
) -> APIRouter:
    """Build the router of HTML views and HTMX fragments."""
    jinja = create_jinja_environment()
    router = APIRouter()

    # --- Helpers -------------------------------------------------------------

    def available_window() -> tuple[date | None, date | None]:
        ranges = data_service.available_ranges()
        window = ranges.get(FNG_INDICATOR)
        if window is None:
            return None, None
        return window.start, window.end

    def default_form_values() -> dict[str, Any]:
        start, end = available_window()
        defaults = backtest_service.default_params("fear_greed")
        return {
            "available_start": start.isoformat() if start else "",
            "available_end": end.isoformat() if end else "",
            "start_date": start.isoformat() if start else "",
            "end_date": end.isoformat() if end else "",
            "daily_below_threshold": defaults.get("daily_below_threshold", 10),
            "daily_amount_eur": _amount_to_form(defaults.get("daily_amount_eur", "50.00")),
            "weekly_bands": defaults.get("weekly_bands", []),
            "execution_mode": "close_same_day",
        }

    def form_from_config(config: BacktestConfig) -> dict[str, Any]:
        values = default_form_values()
        params = config.strategy_params
        values.update(
            {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
                "execution_mode": config.execution_mode,
                "daily_below_threshold": params.get("daily_below_threshold", 10),
                "daily_amount_eur": _amount_to_form(params.get("daily_amount_eur", "50.00")),
                "weekly_bands": params.get("weekly_bands", []),
            }
        )
        return values

    def fng_series() -> dict[date, Decimal]:
        try:
            series = data_service.repo.indicator_series(indicator=FNG_INDICATOR)
        except LookupError:
            return {}
        return series.to_dict()

    def build_alt_tables(result: BacktestResult) -> dict[str, list[dict[str, Any]]]:
        """Head/tail samples of the curves for the accessible chart tables."""
        curve = result.equity_curve
        head = curve[:ALT_SAMPLE]
        tail = curve[-ALT_SAMPLE:] if len(curve) > ALT_SAMPLE else []
        sample = head + [point for point in tail if point not in head]

        index_values = fng_series()
        index_days = sorted(index_values)
        index_head = index_days[:ALT_SAMPLE]
        index_tail = index_days[-ALT_SAMPLE:] if len(index_days) > ALT_SAMPLE else []
        index_sample = index_head + [day for day in index_tail if day not in index_head]

        return {
            "g1_points": [
                {
                    "day": point.day,
                    "invested": format_eur(point.invested_eur),
                    "value": format_eur(point.portfolio_value_eur),
                    "diff": format_signed_eur(
                        point.portfolio_value_eur - point.invested_eur
                    ),
                }
                for point in sample
            ],
            "g2_points": [
                {
                    "day": day,
                    "value": int(index_values[day]),
                    "label": format_fng_label(index_values[day]),
                }
                for day in index_sample
            ],
            "g4_points": [
                {
                    "day": point.day,
                    "value": format_signed_pct(point.drawdown_pct),
                }
                for point in sample
            ],
        }

    def result_context(result: Any) -> dict[str, Any]:
        """Template context of a finished simulation."""
        rows = build_operation_rows(result.fills)
        reasons = sorted(result.metrics.operations_by_reason)
        return {
            "result": result,
            "metrics": result.metrics,
            "context": {
                "run_id": result.run_id,
                "created_at": result.created_at.isoformat(sep=" ").replace("+00:00", " UTC"),
                "code_version": result.code_version,
                "config_hash": result.config_hash,
                "dataset_hash": result.dataset_hash,
                "result_hash": result.result_hash,
                "start_date": result.config.start_date,
                "end_date": result.config.end_date,
                "execution_mode": result.config.execution_mode,
            },
            "charts": build_chart_specs(result, fng_series()),
            "alt": build_alt_tables(result),
            "rows": rows,
            "reasons": reasons,
            "reason": "all",
            "page": 1,
            "total": len(rows),
            "total_pages": max(1, (len(rows) + 49) // 50),
            "incidents": result.incidents,
        }

    def base_context(request: Request, active_nav: str, **extra: Any) -> dict[str, Any]:
        status = data_service.get_data_status()
        context: dict[str, Any] = {
            "request": request,
            "active_nav": active_nav,
            "status": status,
            "has_data": bool(status.datasets),
        }
        context.update(extra)
        return context

    def render(
        request: Request, name: str, context: dict[str, Any], status_code: int = 200
    ) -> HTMLResponse:
        template = jinja.get_template(name)
        return HTMLResponse(template.render(context), status_code=status_code)

    def latest_result() -> Any:
        runs = backtest_service.list_backtests(limit=1)
        if not runs:
            return None
        return backtest_service.get_backtest(runs[0].run_id)

    def default_config() -> BacktestConfig | None:
        """Reference configuration: strategy defaults over the available window."""
        start, end = available_window()
        if start is None or end is None:
            return None
        return BacktestConfig(
            asset="BTC",
            quote="EUR",
            strategy_id="fear_greed",
            start_date=start,
            end_date=end,
            execution_mode="close_same_day",
            strategy_params=backtest_service.default_params("fear_greed"),
        )

    def toast_html(tone: str, message: str) -> str:
        return jinja.get_template("partials/fragments/toast.html").render(
            tone=tone, message=message
        )

    def with_toast(fragment: str, tone: str, message: str) -> str:
        """Append an out-of-band toast so HTMX can drop it into #toasts."""
        return (
            f"{fragment}"
            f'<div id="toasts" hx-swap-oob="true">{toast_html(tone, message)}</div>'
        )

    # --- GET / ----------------------------------------------------------------

    @router.get("/")
    def panel(request: Request, load_run: str | None = None) -> HTMLResponse:
        result = latest_result()
        form = default_form_values()

        if load_run:
            loaded = backtest_service.get_backtest(load_run)
            if loaded is not None:
                result = loaded
                form = form_from_config(loaded.config)

        if result is None and form["available_start"]:
            # El panel nunca aparece vacío cuando hay datos: se ejecuta la
            # simulación de referencia con los parámetros por defecto.
            config = default_config()
            if config is not None:
                try:
                    result = backtest_service.execute_backtest(config)
                except DomainError:
                    result = None

        context = base_context(request, "panel", form=form, errors=None)
        if result:
            context.update(result_context(result))
        else:
            context["result"] = None
        return render(request, "pages/panel.html", context)

    # --- POST /ui/backtests ---------------------------------------------------

    @router.post("/ui/backtests")
    async def run_simulation(request: Request) -> HTMLResponse:
        form = await request.form()
        errors: list[str] = []
        config: BacktestConfig | None = None

        try:
            raw_params = str(form.get("strategy_params_json") or "").strip()
            if raw_params:
                # El JSON oculto es la fuente de verdad (lo mantiene app.js
                # sincronizado con todos los campos del formulario).
                params = _normalize_params(json.loads(raw_params))
            else:
                # Sin JS: se reconstruye desde los campos escalares.
                params = {
                    "daily_below_threshold": int(
                        str(form.get("daily_below_threshold", "10"))
                    ),
                    "daily_amount_eur": str(
                        _parse_decimal(str(form.get("daily_amount_eur", "0")))
                    ),
                    "weekly_bands": [],
                }

            config = BacktestConfig(
                asset="BTC",
                quote="EUR",
                strategy_id=str(form.get("strategy_id", "fear_greed")),
                start_date=date.fromisoformat(str(form.get("start_date", ""))),
                end_date=date.fromisoformat(str(form.get("end_date", ""))),
                execution_mode=str(form.get("execution_mode", "close_same_day")),  # type: ignore[arg-type]
                strategy_params=params,
            )
        except (ValidationError, InvalidOperation, ValueError, TypeError) as error:
            errors = _spanish_errors(error)

        result = None
        if config is not None:
            try:
                result = backtest_service.execute_backtest(config)
            except DomainError as error:
                errors = _spanish_errors(error)

        if result is None:
            if not errors:
                errors = ["No se pudo ejecutar la simulación."]
            error_fragment = jinja.get_template(
                "partials/fragments/error_summary.html"
            ).render(errors=errors)
            if _is_htmx(request):
                return HTMLResponse(
                    with_toast(error_fragment, "error", "No se pudo ejecutar la simulación")
                )
            context = base_context(
                request, "panel", form=default_form_values(), result=None, errors=errors
            )
            return render(request, "pages/panel.html", context)

        context = base_context(
            request,
            "panel",
            form=form_from_config(result.config),
            result=result,
            errors=None,
        )
        context.update(result_context(result))

        if _is_htmx(request):
            result_template = jinja.get_template(
                "partials/fragments/simulation_result.html"
            )
            message = (
                f"Simulación completada: {result.metrics.total_operations} operaciones, "
                f"{format_eur(result.metrics.total_invested_eur)} invertidos"
            )
            return HTMLResponse(
                with_toast(result_template.render(context), "positive", message)
            )
        return render(request, "pages/panel.html", context)

    # --- GET /backtests -------------------------------------------------------

    @router.get("/backtests")
    def backtests(request: Request) -> HTMLResponse:
        runs = backtest_service.list_backtests(limit=100)
        strategies = {
            item["strategy_id"]: item["name"]
            for item in backtest_service.list_available_strategies()
        }
        rendered = [
            {
                "run_id": run.run_id,
                "created_at": run.created_at,
                "strategy_name": strategies.get(run.config.strategy_id, run.config.strategy_id),
                "config": run.config,
                "metrics": run.metrics,
            }
            for run in runs
        ]
        context = base_context(request, "backtests", runs=rendered)
        return render(request, "pages/backtests.html", context)

    # --- GET /backtests/{run_id} ---------------------------------------------

    @router.get("/backtests/{run_id}")
    def backtest_detail(request: Request, run_id: str) -> HTMLResponse:
        result = backtest_service.get_backtest(run_id)
        if result is None:
            context = base_context(request, "backtests", run_id=run_id)
            return render(request, "pages/not_found.html", context, status_code=404)

        context = base_context(request, "backtests", result=result)
        context.update(result_context(result))
        return render(request, "pages/backtest_detail.html", context)

    # --- GET /ui/operations (paginación y filtros HTMX) -----------------------

    @router.get("/ui/operations")
    def operations(
        request: Request,
        run_id: str | None = None,
        page: int = Query(default=1, ge=1),
        reason: str = "all",
    ) -> HTMLResponse:
        result = (
            backtest_service.get_backtest(run_id) if run_id else latest_result()
        )

        if result is None:
            return HTMLResponse(
                '<div class="c-empty"><p class="c-empty__title">Sin operaciones</p>'
                '<p class="c-empty__text">Todavía no hay ninguna simulación ejecutada.</p></div>'
            )

        rows = filter_rows_by_reason(build_operation_rows(result.fills), reason)
        page_rows, total_pages, safe_page = paginate_rows(rows, page)
        context = {
            "request": request,
            "rows": page_rows,
            "reasons": sorted(result.metrics.operations_by_reason),
            "reason": reason,
            "page": safe_page,
            "total_pages": total_pages,
            "total": len(rows),
        }
        return HTMLResponse(
            jinja.get_template("partials/fragments/operations_table.html").render(context)
        )

    # --- GET /data ------------------------------------------------------------

    @router.get("/data")
    def data_page(request: Request) -> HTMLResponse:
        context = base_context(request, "data")
        return render(request, "pages/data.html", context)

    # --- POST /ui/data/sync ---------------------------------------------------

    @router.post("/ui/data/sync")
    def sync_data(request: Request) -> HTMLResponse:
        try:
            data_service.sync_data()
        except DomainError as error:
            message = f"No se pudo actualizar: {error}"
            return HTMLResponse(
                f'<div class="c-alert c-alert--error" role="alert">{message}</div>'
            )
        context = base_context(request, "data")
        return HTMLResponse(
            jinja.get_template("partials/fragments/data_status.html").render(context)
        )

    # --- Páginas de error -----------------------------------------------------

    @router.get("/404")
    def not_found(request: Request) -> HTMLResponse:
        context = base_context(request, "panel")
        return render(request, "pages/not_found.html", context, status_code=404)

    return router


__all__ = ["create_web_router", "TemplateNotFound"]
