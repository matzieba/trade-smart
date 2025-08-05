import logging, requests, functools, xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# FX helper
# ----------------------------------------------------------------------
@functools.lru_cache(maxsize=64)
def _fx_rate(base: str, quote: str = "USD") -> float:
    """
    Return base/quote spot rate.
    • First try exchangerate.host /convert  (no key required)
    • Fallback: ECB daily XML (EUR base) + triangular conversion
    Result cached in-process via lru_cache.
    """

    base, quote = base.upper(), quote.upper()

    if base == quote:
        return 1.0

    try:
        r = requests.get(
            "https://api.exchangerate.host/convert",
            params={"from": base, "to": quote},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("result") is not None:
            return float(data["result"])
        logger.warning("exchangerate.host returned no 'result': %s", data)
    except Exception as exc:
        logger.warning("exchangerate.host failed (%s) – using ECB fallback.", exc)

    # 2️⃣  fallback – ECB EUR-based basket  ---------------------------
    try:
        xml_raw = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=8,
        ).text
        tree = ET.fromstring(xml_raw)

        # Build dict: currency -> rate vs EUR
        eur_rates = {
            cube.attrib["currency"]: float(cube.attrib["rate"])
            for cube in tree.iter(
                "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}Cube"
            )
            if "currency" in cube.attrib
        }
        eur_rates["EUR"] = 1.0  # make life easier

        if base not in eur_rates or quote not in eur_rates:
            raise RuntimeError(f"ECB feed missing {base} or {quote}")

        # EUR is the pivot: base/quote = (EUR/quote) / (EUR/base)
        return eur_rates[quote] / eur_rates[base]

    except Exception as exc:
        logger.error("ECB fallback failed as well: %s", exc)
        raise RuntimeError("Unable to obtain FX rate") from exc


# ----------------------------------------------------------------------
# Node executed inside LangGraph
# ----------------------------------------------------------------------
def convert_amount(state: dict) -> dict:
    """
    • Reads optimiser weights from state['optimised_portfolio']
    • Converts user amount (state['intent']) into USD cash buckets
    • Writes 'portfolio' back into state
    """

    logger.info("Converting amount according to weights …")

    weights = state.get("optimised_portfolio") or {}
    if not weights:
        logger.warning("No weights present – skipping FX conversion.")
        return state

    amount_home = state["intent"]["amount"]
    home_ccy = state["intent"]["currency"]

    # Single hop: home_ccy -> USD
    fx_home_usd = _fx_rate(home_ccy, "USD")
    logger.debug("FX %s/USD = %.6f", home_ccy, fx_home_usd)

    draft = []
    for sym, w in weights.items():
        if w <= 0:
            continue
        cash_home = amount_home * w
        cash_usd = cash_home * fx_home_usd

        draft.append(
            {
                "ticker": sym,
                "cash_usd": round(cash_usd, 2),
                "weight_pct": round(w * 100, 2),
            }
        )

    logger.info("FX conversion done → %s", draft)
    return {"optimised_portfolio": draft}
