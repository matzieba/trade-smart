from django.db import models
from model_utils.models import TimeStampedModel


class TechnicalIndicator(TimeStampedModel):
    """One row per (ticker, date, indicator).  Keep it generic."""

    ticker = models.CharField(max_length=10, db_index=True)
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=32)  # e.g. 'SMA_50'
    value = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        unique_together = ("ticker", "date", "name")
        ordering = ("-date",)
