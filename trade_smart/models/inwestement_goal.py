from django.contrib.auth.models import User
from django.db import models


class InvestmentGoal(models.Model):
    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PLN")
    horizon_months = models.PositiveIntegerField(default=12)
    risk_level = models.CharField(max_length=6, choices=RISK_CHOICES, default="medium")
    status = models.CharField(max_length=10, default="NEW")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
