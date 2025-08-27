import requests
import pandas as pd

POLYGON_API_KEY = "D2ss7P80Pm42ShCqcexGaZUD59IaKR9M"

def fetch_options(symbol: str, min_dte: int, max_dte: int, min_delta: float, max_delta: float):
    """
    Fetch options contracts from Polygon API with filters.
    """
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={POLYGON_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Polygon API error {response.status_code}: {response.text}")

    data = response.json()
    contracts = []

    # Extract contracts safely
    if "results" in data and isinstance(data["results"], dict):
        contracts = data["results"].get("options", [])
    elif "results" in data and isinstance(data["results"], list):
        contracts = data["results"]
    else:
        raise Exception("Unexpected response format from Polygon API")

    filtered = []
    for c in contracts:
        details = c.get("details", {})
        greeks = c.get("greeks", {})
        quote = c.get("last_quote", {})

        # Calculate DTE (days to expiration)
        exp_date = details.get("expiration_date")
        dte = None
        if exp_date:
            try:
                dte = (pd.to_datetime(exp_date) - pd.Timestamp.today()).days
            except Exception:
                dte = None

        row = {
            "symbol": details.get("symbol"),
            "type": details.get("contract_type"),
            "strike": details.get("strike_price"),
            "expiration": exp_date,
            "dte": dte,
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "iv": greeks.get("iv"),
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
            "last_price": quote.get("last"),
        }

        # Apply filters
        if row["dte"] is not None and (min_dte <= row["dte"] <= max_dte):
            if row["delta"] is not None and (min_delta <= row["delta"] <= max_delta):
                filtered.append(row)

    return pd.DataFrame(filtered)
