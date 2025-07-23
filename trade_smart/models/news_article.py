from django.db import models
from model_utils.models import TimeStampedModel


class NewsArticle(TimeStampedModel):
    ticker = models.CharField(max_length=12, db_index=True)
    headline = models.TextField()
    source = models.CharField(max_length=60)
    url = models.URLField(max_length=300)
    published_at = models.DateTimeField(db_index=True)
    sentiment = models.DecimalField(max_digits=4, decimal_places=3, null=True)

    # we keep vector only in Chroma → not in SQL
    class Meta:
        indexes = [models.Index(fields=["ticker", "-published_at"])]
        unique_together = ("url", "published_at")
