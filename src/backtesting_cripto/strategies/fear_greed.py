"""Fear & Greed accumulation strategy (plan section E.4).

Daily rule (index below the threshold, default < 10) always prevails,
even on Mondays. The weekly bands only apply on Mondays. A day without
an index reading (the 39 historical gaps) never produces an order.
"""

from collections.abc import Iterator

from pydantic import BaseModel, ValidationError

from backtesting_cripto.domain.contracts import StrategyContext
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError
from backtesting_cripto.domain.models import FearGreedParams, OrderIntent
from backtesting_cripto.engine.calendar import is_monday, iter_days
from backtesting_cripto.strategies.base import StrategyMetadata, register_strategy

STRATEGY_ID = "fear_greed"
STRATEGY_NAME = "Acumulación por Crypto Fear & Greed Index"
STRATEGY_DESCRIPTION = (
    "Compra semanal los lunes según los tramos del índice Fear & Greed, "
    "más una compra diaria cuando el índice cae por debajo del umbral."
)
INDICATOR_NAME = "fear_greed"


class FearGreedStrategy:
    """Accumulation strategy driven by the Crypto Fear & Greed Index."""

    strategy_id = STRATEGY_ID
    name = STRATEGY_NAME
    required_indicators: tuple[str, ...] = (INDICATOR_NAME,)
    params_schema: type[BaseModel] = FearGreedParams

    def generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]:
        """Yield one order intent per buy opportunity inside the window."""
        try:
            params = FearGreedParams.model_validate(ctx.params)
        except ValidationError as error:
            msg = f"invalid {STRATEGY_ID} parameters: {error}"
            raise ConfigurationError(msg) from error

        indicator = ctx.indicators.get(INDICATOR_NAME)
        if indicator is None:
            msg = f"missing required indicator: {INDICATOR_NAME}"
            raise InsufficientDataError(msg)

        for day in iter_days(ctx.start_date, ctx.end_date):
            value = indicator.value_on(day)
            if value is None:
                # Historical gap in the index: no data, no purchase.
                continue

            # 1) Daily rule prevails over any weekly band, even on Mondays.
            if value < params.daily_below_threshold:
                yield OrderIntent(
                    decision_day=day,
                    asset=ctx.asset,
                    amount_eur=params.daily_amount_eur,
                    reason=f"daily_<{params.daily_below_threshold}",
                    index_value=value,
                )
                continue

            # 2) Weekly bands are only evaluated on Mondays.
            if is_monday(day):
                for band in sorted(params.weekly_bands, key=lambda band: band.min_value):
                    if band.min_value <= value <= band.max_value:
                        yield OrderIntent(
                            decision_day=day,
                            asset=ctx.asset,
                            amount_eur=band.amount_eur,
                            reason=f"monday_{band.min_value}_{band.max_value}",
                            index_value=value,
                        )
                        break
            # 3) Above every band: no purchase.


def register() -> StrategyMetadata:
    """Register the strategy in the default registry."""
    return register_strategy(FearGreedStrategy(), description=STRATEGY_DESCRIPTION)
