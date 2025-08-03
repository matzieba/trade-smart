import logging

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


from trade_smart.models import InvestmentGoal
from trade_smart.poractive_proposition.graph import build_graph
from trade_smart.poractive_proposition.serializers import (
    InvestmentGoalSerializer,
    ProposalRequestSerializer,
)

logger = logging.getLogger(__name__)


class InvestmentGoalViewSet(viewsets.ModelViewSet):
    serializer_class = InvestmentGoalSerializer
    # permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return InvestmentGoal.objects.filter(user=self.request.user)

    def perform_create(self, serializer, run_proactive_proposition=None):
        obj = serializer.save(user=self.request.user, status="NEW")
        run_proactive_proposition.delay(obj.id)


@api_view(["POST"])
@permission_classes([AllowAny])
def propose(request):
    serializer = ProposalRequestSerializer(data=request.data)
    if serializer.is_valid():
        logger.info(f"Received request with data: {serializer.validated_data}")
        graph = build_graph()
        try:
            output = graph.invoke({"user_request": serializer.validated_data})
            logger.info(f"Successfully processed request with output: {output}")
            return Response(output)
        except Exception as exc:
            logger.error(f"Error processing request: {exc}", exc_info=True)
            return Response({"error": str(exc)}, status=500)
    else:
        logger.warning(f"Invalid request data: {serializer.errors}")
    return Response(serializer.errors, status=400)
