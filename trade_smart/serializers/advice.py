from rest_framework import serializers

from trade_smart.models import Advice


class AdviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advice
        fields = ("id", "ticker", "action", "confidence", "rationale", "created")
