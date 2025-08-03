from rest_framework import serializers

from trade_smart.models import InvestmentGoal


class InvestmentGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentGoal
        fields = "__all__"
        read_only_fields = ("status", "created_at", "updated_at", "user")
