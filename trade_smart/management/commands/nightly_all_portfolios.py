from django.core.management import BaseCommand
from django.db import transaction

from trade_smart.models import Position, MarketData
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
        # fetch_daily_ohlcv('ETFBCASH.WA')
        # fetch_all_tickers()
        # compute_all_indicators()
        # nightly_all_portfolios()
        # fetch_news_for_all_positions()
        issue_portfolio_advice(2)
        # compute_indicators('ETFBCASH.WA')
