import requests, itertools, os, pandas as pd
from concurrent.futures import ThreadPoolExecutor

YF_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/"
SCREENS = [
    "most_actives",
    "day_gainers",
    "day_losers",
    "undervalued_growth",
    "undervalued_large_caps",
]
REGIONS = ["US", "DE", "GB", "FR", "IN", "HK", "AU", "CA"]


def _one_req(screen, region):
    r = requests.get(
        YF_URL,
        params={"scrIds": screen, "count": 30, "region": region},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()["finance"]["result"][0]["quotes"]
    return [x["symbol"] for x in items]


def get_hot_tickers(state):
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [
            ex.submit(_one_req, s, r) for s, r in itertools.product(SCREENS, REGIONS)
        ]
    tickers = set(itertools.chain.from_iterable(f.result() for f in futs))
    capped = list(tickers)[:120]
    return {**state, "candidates": capped}
