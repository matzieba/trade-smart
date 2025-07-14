from decimal import Decimal
from django.db import models
from model_utils.models import TimeStampedModel
from trade_smart.models.portfolio import Portfolio


class Advice(TimeStampedModel):
    ACTIONS = (
        ("BUY", "BUY"),
        ("SELL", "SELL"),
        ("HOLD", "HOLD"),
        ("REBAL", "REBALANCE"),
    )
    portfolio = models.ForeignKey(
        Portfolio, related_name="advices", on_delete=models.CASCADE
    )
    ticker = models.CharField(max_length=10, blank=True)  # empty = whole PF
    action = models.CharField(max_length=5, choices=ACTIONS)
    confidence = models.DecimalField(max_digits=4, decimal_places=3)  # 0-1
    rationale = models.TextField()
