from rest_framework import permissions, viewsets

from trade_smart.models import Position
from trade_smart.serializers import PositionSerializer


class PositionViewSet(viewsets.ModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Position.objects.filter(portfolio__user=self.request.user)
