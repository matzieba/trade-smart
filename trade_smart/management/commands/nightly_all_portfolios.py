from django.core.management import BaseCommand

from trade_smart.tasks import nightly_all_portfolios, fetch_all_tickers


class Command(BaseCommand):

    def handle(self, *args, **options):
        # fetch_all_tickers()
        nightly_all_portfolios()
