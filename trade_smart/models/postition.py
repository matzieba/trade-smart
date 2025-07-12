from django.db import models
from model_utils.models import TimeStampedModel

from trade_smart.models import Portfolio


class Position(TimeStampedModel):
    portfolio = models.ForeignKey(
        Portfolio, related_name="positions", on_delete=models.CASCADE
    )
    ticker = models.CharField(max_length=12)
    qty = models.DecimalField(max_digits=18, decimal_places=4)
    avg_price = models.DecimalField(max_digits=20, decimal_places=4)
    target_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticker} x{self.qty}"
