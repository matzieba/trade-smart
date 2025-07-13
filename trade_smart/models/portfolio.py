from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from model_utils.models import TimeStampedModel


class Portfolio(TimeStampedModel):
    user = models.ForeignKey(
        User,
        related_name="portfolios",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=120)

    def market_value(self) -> Decimal:
        """Sum(qty * last close)  – helper used by the analyzer"""
        from .market_data import MarketData  # local import to avoid cycle

        latest_px = (
            MarketData.objects.filter(
                ticker__in=self.positions.values_list("ticker", flat=True)
            )
            .order_by("ticker", "-date")
            .distinct("ticker")  # ⇐ Postgres only
            .values("ticker", "close")
        )
        px_map = {row["ticker"]: row["close"] for row in latest_px}
        return sum(
            pos.qty * px_map.get(pos.ticker, Decimal("0"))
            for pos in self.positions.all()
        )
