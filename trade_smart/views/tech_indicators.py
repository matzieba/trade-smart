from rest_framework.response import Response
from rest_framework.decorators import api_view

from trade_smart.analytics.portfolio_analyser import analyse
from trade_smart.models import Portfolio


@api_view(["GET"])
def portfolio_metrics(request, pk: int):
    portfolio = Portfolio.objects.get(pk=pk, user=request.user)
    return Response(analyse(portfolio))
