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
)


class Command(BaseCommand):

    def handle(self, *args, **options):
        # fetch_daily_ohlcv('VVSM.HA')
        # fetch_all_tickers()
        # nightly_all_portfolios()
        # fetch_news_for_all_positions()
        # issue_portfolio_advice(2)
        for position in Position.objects.all():
            print(position.ticker)
            ticker = position.ticker
            df = _download_ohlcv(ticker)
            if df.empty:
                return f"No data for {ticker}"

            objects = _df_to_objects(df, ticker)
            if not objects:
                return f"No valid rows for {ticker}"

            with transaction.atomic():
                MarketData.objects.bulk_create(
                    objects,
                    update_conflicts=True,
                    update_fields=["open", "high", "low", "close", "volume"],
                    unique_fields=["ticker", "date"],
                )

            msg = f"Stored {len(objects)} OHLCV rows for {ticker}"
            logger.info(msg)
