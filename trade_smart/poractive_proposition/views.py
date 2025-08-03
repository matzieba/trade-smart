from rest_framework import viewsets

from trade_smart.models import InvestmentGoal
from trade_smart.poractive_proposition.serializers import InvestmentGoalSerializer


class InvestmentGoalViewSet(viewsets.ModelViewSet):
    serializer_class = InvestmentGoalSerializer
    # permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return InvestmentGoal.objects.filter(user=self.request.user)

    def perform_create(self, serializer, run_proactive_proposition=None):
        obj = serializer.save(user=self.request.user, status="NEW")
        run_proactive_proposition.delay(obj.id)
