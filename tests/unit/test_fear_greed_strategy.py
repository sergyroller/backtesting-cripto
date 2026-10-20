"""Unit tests for the Fear & Greed strategy and the strategy registry."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backtesting_cripto.domain.contracts import StrategyContext
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError
from backtesting_cripto.domain.models import FearGreedParams
from backtesting_cripto.strategies import (
    FearGreedStrategy,
    StrategyRegistry,
    default_registry,
    get_strategy,
    list_strategies,
    register_strategy,
)
from backtesting_cripto.strategies.base import StrategyMetadata
from backtesting_cripto.strategies.fear_greed import STRATEGY_ID

MONDAY = date(2024, 1, 1)
TUESDAY = date(2024, 1, 2)


class FakeIndicatorSeries:
    """IndicatorSeries backed by a dict of day → value."""

    def __init__(self, values: dict[date, Decimal]) -> None:
        self._values = dict(sorted(values.items()))
        self._days = list(self._values)

    def value_on(self, day: date) -> Decimal | None:
        return self._values.get(day)

    def date_bounds(self) -> tuple[date, date]:
        return self._days[0], self._days[-1]


def make_context(
    day: date,
    value: str | None,
    params: dict[str, object] | None = None,
) -> StrategyContext:
    values = {} if value is None else {day: Decimal(value)}
    return StrategyContext(
        asset="BTC",
        start_date=day,
        end_date=day,
        params=params or {},
        indicators={"fear_greed": FakeIndicatorSeries(values)},
    )


def intents_for(day: date, value: str | None, params: dict[str, object] | None = None) -> list:
    from backtesting_cripto.domain.models import OrderIntent

    result: list[OrderIntent] = list(
        FearGreedStrategy().generate_intents(make_context(day, value, params))
    )
    return result


# --- Monday band edges (plan section G.1) -------------------------------------


@pytest.mark.parametrize(
    ("value", "expected_amount", "expected_reason"),
    [
        ("9", "50.00", "daily_<10"),
        ("10", "200.00", "monday_10_14"),
        ("14", "200.00", "monday_10_14"),
        ("15", "150.00", "monday_15_19"),
        ("19", "150.00", "monday_15_19"),
        ("20", "100.00", "monday_20_24"),
        ("24", "100.00", "monday_20_24"),
    ],
)
def test_monday_band_edges(value: str, expected_amount: str, expected_reason: str) -> None:
    intents = intents_for(MONDAY, value)
    assert len(intents) == 1
    assert intents[0].amount_eur == Decimal(expected_amount)
    assert intents[0].reason == expected_reason
    assert intents[0].decision_day == MONDAY
    assert intents[0].index_value == Decimal(value)


def test_monday_above_all_bands_emits_nothing() -> None:
    assert intents_for(MONDAY, "25") == []


def test_daily_rule_prevails_on_monday() -> None:
    intents = intents_for(MONDAY, "8")
    assert len(intents) == 1
    assert intents[0].amount_eur == Decimal("50.00")
    assert intents[0].reason == "daily_<10"


# --- Weekdays -----------------------------------------------------------------


def test_weekday_inside_weekly_band_emits_nothing() -> None:
    assert intents_for(TUESDAY, "12") == []


def test_weekday_below_threshold_buys_daily() -> None:
    intents = intents_for(TUESDAY, "7")
    assert len(intents) == 1
    assert intents[0].amount_eur == Decimal("50.00")
    assert intents[0].reason == "daily_<10"


def test_monday_without_index_value_emits_nothing() -> None:
    assert intents_for(MONDAY, None) == []


# --- Custom parameters --------------------------------------------------------


def test_custom_widened_band() -> None:
    params: dict[str, object] = {
        "weekly_bands": [
            {"min_value": 10, "max_value": 14, "amount_eur": "200.00"},
            {"min_value": 15, "max_value": 19, "amount_eur": "150.00"},
            {"min_value": 20, "max_value": 30, "amount_eur": "120.00"},
        ]
    }
    intents = intents_for(MONDAY, "28", params)
    assert len(intents) == 1
    assert intents[0].amount_eur == Decimal("120.00")
    assert intents[0].reason == "monday_20_30"


def test_custom_daily_threshold_and_amount() -> None:
    params: dict[str, object] = {
        "daily_below_threshold": 8,
        "daily_amount_eur": "75.50",
    }
    intents = intents_for(TUESDAY, "7", params)
    assert len(intents) == 1
    assert intents[0].amount_eur == Decimal("75.50")
    assert intents[0].reason == "daily_<8"


def test_daily_threshold_above_weekly_bands_is_rejected() -> None:
    # Raising the daily threshold above the default band minimum (10) is
    # rejected by FearGreedParams, as the bands would invade the threshold.
    params: dict[str, object] = {
        "daily_below_threshold": 15,
        "daily_amount_eur": "75.50",
    }
    with pytest.raises(ConfigurationError):
        intents_for(TUESDAY, "12", params)


def test_overlapping_bands_raise_configuration_error() -> None:
    params: dict[str, object] = {
        "weekly_bands": [
            {"min_value": 10, "max_value": 14, "amount_eur": "200.00"},
            {"min_value": 14, "max_value": 19, "amount_eur": "150.00"},
        ]
    }
    with pytest.raises(ConfigurationError):
        intents_for(MONDAY, "15", params)


def test_missing_indicator_raises_insufficient_data() -> None:
    ctx = StrategyContext(
        asset="BTC",
        start_date=MONDAY,
        end_date=MONDAY,
        params={},
        indicators={},
    )
    with pytest.raises(InsufficientDataError):
        list(FearGreedStrategy().generate_intents(ctx))


# --- Mixed week integration ---------------------------------------------------


def test_mixed_week_emits_expected_intents() -> None:
    week = [
        (date(2024, 1, 1), "12"),  # Monday, band 10-14
        (date(2024, 1, 2), "7"),  # Tuesday, daily
        (date(2024, 1, 3), "15"),  # Wednesday, no band outside Monday
        (date(2024, 1, 4), "8"),  # Thursday, daily
        (date(2024, 1, 5), "25"),  # Friday, above all bands
        (date(2024, 1, 6), "20"),  # Saturday, bands only on Monday
        (date(2024, 1, 7), "22"),  # Sunday, bands only on Monday
    ]
    indicator = FakeIndicatorSeries({day: Decimal(value) for day, value in week})
    ctx = StrategyContext(
        asset="BTC",
        start_date=week[0][0],
        end_date=week[-1][0],
        params={},
        indicators={"fear_greed": indicator},
    )

    intents = list(FearGreedStrategy().generate_intents(ctx))

    assert [(intent.decision_day, intent.reason) for intent in intents] == [
        (date(2024, 1, 1), "monday_10_14"),
        (date(2024, 1, 2), "daily_<10"),
        (date(2024, 1, 4), "daily_<10"),
    ]


# --- Registry -----------------------------------------------------------------


def test_default_registry_contains_fear_greed() -> None:
    strategy = get_strategy(STRATEGY_ID)
    assert strategy.strategy_id == STRATEGY_ID
    assert strategy.name == "Acumulación por Crypto Fear & Greed Index"
    assert strategy.required_indicators == ("fear_greed",)

    metadata = default_registry.metadata(STRATEGY_ID)
    assert isinstance(metadata, StrategyMetadata)
    assert metadata.params_schema is FearGreedParams
    assert metadata.required_indicators == ("fear_greed",)

    assert STRATEGY_ID in [item.strategy_id for item in list_strategies()]


def test_registry_get_unknown_strategy_raises() -> None:
    with pytest.raises(ConfigurationError, match="unknown strategy_id"):
        get_strategy("does_not_exist")


def test_registry_validates_params() -> None:
    params = default_registry.validate_params(STRATEGY_ID, {})
    assert isinstance(params, FearGreedParams)
    assert params.daily_amount_eur == Decimal("50.00")


def test_registry_rejects_strategy_without_params_schema() -> None:
    class NoSchemaStrategy:
        strategy_id = "no_schema"
        name = "No schema"
        required_indicators: tuple[str, ...] = ()

        def generate_intents(self, ctx: StrategyContext):  # type: ignore[no-untyped-def]
            return iter(())

    with pytest.raises(ConfigurationError, match="params_schema"):
        register_strategy(NoSchemaStrategy())  # type: ignore[arg-type]


def test_registry_register_replaces_entry() -> None:
    registry = StrategyRegistry()
    first = registry.register(FearGreedStrategy(), description="first")
    second = registry.register(FearGreedStrategy(), description="second")

    assert first.strategy_id == second.strategy_id == STRATEGY_ID
    assert registry.metadata(STRATEGY_ID).description == "second"
    assert len(registry.list()) == 1


def test_fear_greed_params_model_round_trip() -> None:
    params = FearGreedParams()
    payload = params.model_dump(mode="json")
    assert FearGreedParams.model_validate(payload) == params

    with pytest.raises(ValidationError):
        FearGreedParams.model_validate({"daily_below_threshold": 101})
