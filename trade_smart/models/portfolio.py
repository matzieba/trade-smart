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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user})"
