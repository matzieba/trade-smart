from rest_framework import permissions, viewsets

from trade_smart.models import Portfolio
from trade_smart.serializers import PortfolioSerializer


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]


def get_queryset(self):
    return Portfolio.objects.filter(user=self.request.user)


def perform_create(self, serializer):
    serializer.save(user=self.request.user)
