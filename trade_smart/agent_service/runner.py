from trade_smart.agent_service.graph import build_graph
from trade_smart.models.advice import Advice
from trade_smart.models.portfolio import Portfolio


graph = build_graph()


def run_for_portfolio(pf: Portfolio):
    for pos in pf.positions.all():
        state = graph.invoke({"ticker": pos.ticker, "portfolio": pf})
        adv = state["advice"]
        Advice.objects.update_or_create(
            portfolio=pf,
            ticker=pos.ticker,
            defaults=dict(
                action=adv["action"],
                confidence=adv["confidence"],
                rationale=adv["rationale"],
            ),
        )
