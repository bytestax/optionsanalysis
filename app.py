import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --------------------
# CONFIG
# --------------------
API_KEY = "D2ss7P80Pm42ShCqcexGaZUD59IaKR9M"
BASE_URL = "https://api.polygon.io"

# --------------------
# FUNCTIONS
# --------------------
def fetch_options_chain(symbol):
    """Fetch snapshot option chain from Polygon"""
    url = f"{BASE_URL}/v3/snapshot/options/{symbol}"
    params = {"apiKey": API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    return data.get("results", {})


def process_options(data, min_dte, max_dte, min_delta, max_delta):
    """Filter options data by user inputs"""
    options = []
    now = datetime.now()

    for opt in data.get("options", []):
        details = opt.get("details", {})
        greeks = opt.get("greeks", {})
        last_quote = opt.get("last_quote", {})
        last_trade = opt.get("last_trade", {})

        # Expiration & DTE
        exp = details.get("expiration_date")
        if not exp:
            continue
        dte = (datetime.fromisoformat(exp) - now).days
        if not (min_dte <= dte <= max_dte):
            continue

        # Delta filter
        delta = greeks.get("delta")
        if delta is None:
            continue
        if not (min_delta <= delta <= max_delta):
            continue

        # Collect row
        options.append({
            "symbol": details.get("ticker"),
            "type": details.get("contract_type"),
            "strike": details.get("strike_price"),
            "expiration": exp,
            "dte": dte,
            "delta": round(delta, 4),
            "gamma": round(greeks.get("gamma", 0), 4),
            "theta": round(greeks.get("theta", 0), 4),
            "vega": round(greeks.get("vega", 0), 4),
            "iv": round(greeks.get("iv", 0), 4),
            "bid": last_quote.get("bid", None),
            "ask": last_quote.get("ask", None),
            "last_price": last_trade.get("price", None),
        })

    df = pd.DataFrame(options)

    # Sort by closest strikes to ATM
    if not df.empty:
        df = df.sort_values(by=["expiration", "strike"]).reset_index(drop=True)

    return df

# --------------------
# STREAMLIT UI
# --------------------
st.title("📊 Options Analyzer")

symbol = st.text_input("Enter Symbol (default: SPY)", value="SPY").upper()
min_dte = st.number_input("Min DTE", value=30)
max_dte = st.number_input("Max DTE", value=60)
min_delta = st.number_input("Min Delta", value=-0.3)
max_delta = st.number_input("Max Delta", value=0.3)

if st.button("Fetch Options"):
    st.info("Fetching option contracts...")
    try:
        raw = fetch_options_chain(symbol)
        df = process_options(raw, min_dte, max_dte, min_delta, max_delta)

        if df.empty:
            st.warning("⚠️ No options matched your filters. Try adjusting delta or DTE range.")
        else:
            st.success(f"✅ Found {len(df)} matching option contracts")
            st.dataframe(df)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
