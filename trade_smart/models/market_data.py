from django.db import models
from model_utils.models import TimeStampedModel


class MarketData(TimeStampedModel):
    ticker = models.CharField(max_length=10, db_index=True)
    date = models.DateField(db_index=True)
    open = models.DecimalField(max_digits=20, decimal_places=4)
    high = models.DecimalField(max_digits=20, decimal_places=4)
    low = models.DecimalField(max_digits=20, decimal_places=4)
    close = models.DecimalField(max_digits=20, decimal_places=4)
    volume = models.BigIntegerField()

    class Meta:
        unique_together = ("ticker", "date")
        ordering = ("-date",)
