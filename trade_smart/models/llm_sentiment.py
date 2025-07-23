from django.db import models
from model_utils.models import TimeStampedModel


class LLMSentiment(TimeStampedModel):
    ticker = models.CharField(max_length=12, db_index=True)
    score = models.DecimalField(max_digits=4, decimal_places=3)
    summary = models.TextField()

    class Meta:
        verbose_name = "LLM Sentiment"
        verbose_name_plural = "LLM Sentiments"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.ticker} - {self.score} ({self.created.date()})"
