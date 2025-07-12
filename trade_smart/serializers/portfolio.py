from rest_framework import serializers

from trade_smart.models import Portfolio


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = "__all__"
