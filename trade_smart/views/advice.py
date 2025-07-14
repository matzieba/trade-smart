from rest_framework import generics

from trade_smart.models import Advice
from trade_smart.serializers.advice import AdviceSerializer


class AdviceList(generics.ListAPIView):
    serializer_class = AdviceSerializer

    def get_queryset(self):
        pf_id = self.kwargs["pk"]
        return Advice.objects.filter(
            portfolio_id=pf_id, portfolio__user=self.request.user
        ).order_by("-created")
