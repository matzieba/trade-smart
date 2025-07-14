from rest_framework import serializers

from trade_smart.models import TechnicalIndicator


class TechIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicalIndicator
        fields = ("date", "name", "value")
