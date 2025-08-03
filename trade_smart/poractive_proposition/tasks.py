from celery import shared_task
import httpx, os, json

from trade_smart.models import Advice
from trade_smart.models.inwestement_goal import InvestmentGoal

AGENT_SVC = os.getenv("AGENT_SVC_URL", "http://localhost:8000/advice")


@shared_task
def run_proactive_proposition(goal_id: int):
    goal = InvestmentGoal.objects.get(id=goal_id)

    payload = {
        "amount": float(goal.amount),
        "currency": goal.currency,
        "horizon": goal.horizon_months,
        "risk": goal.risk_level,
    }
    with httpx.Client(timeout=180) as client:
        res = client.post(f"{AGENT_SVC}/propose", json=payload)
        res.raise_for_status()
    data = res.json()

    for row in data["portfolio"]:
        Advice.objects.create(
            user=goal.user,
            goal=goal,
            ticker=row["ticker"],
            action="BUY",
            confidence=row["confidence"],
            rationale=row["rationale"],
            weight_pct=row["weight_pct"],
        )

    goal.status = "DONE"
    goal.save()

    # Optional: push websocket notification
