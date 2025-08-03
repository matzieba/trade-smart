from rest_framework import serializers

from trade_smart.models import InvestmentGoal


class InvestmentGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentGoal
        fields = "__all__"
        read_only_fields = ("status", "created_at", "updated_at", "user")


class ProposalRequestSerializer(serializers.Serializer):
    amount = serializers.FloatField(min_value=0)
    currency = serializers.CharField(min_length=3, max_length=3)
    horizon = serializers.IntegerField(min_value=1)
    risk = serializers.ChoiceField(choices=["low", "medium", "high"])
