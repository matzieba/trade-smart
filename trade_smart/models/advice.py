from django.contrib.auth.models import User
from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel

from trade_smart.models import Portfolio
from trade_smart.models.inwestement_goal import InvestmentGoal


class Advice(TimeStampedModel):
    ACTIONS = Choices("BUY", "SELL", "HOLD")
    portfolio = models.ForeignKey(
        Portfolio, related_name="advices", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)
    goal = models.ForeignKey(
        InvestmentGoal, on_delete=models.CASCADE, null=True, blank=True
    )
    ticker = models.CharField(max_length=12)
    action = models.CharField(choices=ACTIONS, max_length=4)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    rationale = models.TextField()
    weight_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.action} {self.ticker} for {self.user.username}"
