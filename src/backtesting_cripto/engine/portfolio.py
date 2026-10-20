"""Portfolio accumulating executed fills."""

from datetime import date
from decimal import Decimal

from backtesting_cripto.domain.models import Fill, quantize_btc, quantize_eur


class Portfolio:
    """Accumulates executed fills: invested capital and BTC balance."""

    def __init__(self) -> None:
        self._fills: list[Fill] = []
        self._total_invested_eur = Decimal("0.00")
        self._btc_accumulated = Decimal("0.00000000")

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    @property
    def total_invested_eur(self) -> Decimal:
        return self._total_invested_eur

    @property
    def btc_accumulated(self) -> Decimal:
        return self._btc_accumulated

    def apply(self, fill: Fill) -> None:
        """Register an executed fill and update the accumulated state."""
        self._fills.append(fill)
        self._total_invested_eur = quantize_eur(self._total_invested_eur + fill.amount_eur)
        self._btc_accumulated = quantize_btc(self._btc_accumulated + fill.btc_quantity)

    def state_on_or_before(self, day: date) -> tuple[Decimal, Decimal]:
        """(invested_eur, btc_accumulated) from fills executed on or before day."""
        invested = Decimal("0.00")
        btc = Decimal("0.00000000")
        for fill in self._fills:
            if fill.execution_day <= day:
                invested += fill.amount_eur
                btc += fill.btc_quantity
        return quantize_eur(invested), quantize_btc(btc)
