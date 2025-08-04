from django.core.management import BaseCommand
from django.db import transaction

from trade_smart.agent_service.runner import graph
from trade_smart.models import Position, MarketData, Portfolio, Advice
from trade_smart.tasks import (
    nightly_all_portfolios,
    fetch_all_tickers,
    fetch_news_for_all_positions,
    issue_portfolio_advice,
    fetch_daily_ohlcv,
    _download_ohlcv,
    _df_to_objects,
    logger,
    compute_indicators,
    compute_all_indicators,
)


class Command(BaseCommand):

    def handle(self, *args, **options):
        # fetch_daily_ohlcv('SPY')
        # fetch_all_tickers()
        # compute_all_indicators()
        # nightly_all_portfolios()
        # fetch_news_for_all_positions()
        issue_portfolio_advice(2)
        # compute_indicators('ETFBCASH.WA')
        # advice_for_ticker('JSW.PL')


def advice_for_ticker(ticker):
    pf = Portfolio.objects.get(id=1)
    try:
        state = graph.invoke({"ticker": ticker, "portfolio": pf})
        adv = state["advice"]
        Advice.objects.update_or_create(
            portfolio=pf,
            ticker=ticker,
            defaults=dict(
                action=adv["action"],
                confidence=adv["confidence"],
                rationale=adv["rationale"],
            ),
        )
    except Exception as e:
        print(f"Error evaluating position {ticker} for portfolio {pf.id}: {e}")
        all_evaluated = False
