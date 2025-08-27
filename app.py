import streamlit as st
import requests
import pandas as pd
import datetime

# ---- CONFIG ----
API_KEY = st.secrets.get("POLYGON_API_KEY", "YOUR_API_KEY_HERE")  # use Streamlit secrets if deployed

# ---- HELPERS ----
def fetch_options_contracts(symbol, min_dte, max_dte, min_delta, max_delta, use_abs_delta=True):
    url = "https://api.polygon.io/v3/reference/options/contracts"
    today = datetime.date.today()
    start_date = today + datetime.timedelta(days=min_dte)
    end_date = today + datetime.timedelta(days=max_dte)

    params = {
        "underlying_ticker": symbol,
        "as": "",  # keep empty
        "expiration_date.gte": start_date.strftime("%Y-%m-%d"),
        "expiration_date.lte": end_date.strftime("%Y-%m-%d"),
        "limit": 1000,
        "order": "asc",
        "sort": "ticker",
        "apiKey": API_KEY,   # ✅ FIX: always append apiKey
    }

    all_contracts = []
    while True:
        resp = requests.get(url, params=params)
        if resp.status_code == 401:
            st.error("🚨 Unauthorized: Check your Polygon API key or subscription plan.")
            return []
        resp.raise_for_status()
        data = resp.json()

        contracts = data.get("results", [])
        if not contracts:
            break

        for c in contracts:
            # Greeks are not included here → need a separate call
            all_contracts.append({
                "ticker": c.get("ticker"),
                "expiration": c.get("expiration_date"),
                "strike": c.get("strike_price"),
                "contract_type": c.get("contract_type"),
            })

        # Pagination
        next_url = data.get("next_url")
        if not next_url:
            break
        url = next_url + f"&apiKey={API_KEY}"  # ✅ FIX: ensure apiKey is in pagination too
        params = {}

    return all_contracts


# ---- STREAMLIT APP ----
st.title("📊 Options Chain Explorer (Polygon API)")

symbol = st.text_input("Symbol", "SPY")
min_dte = st.number_input("Min DTE", 1, 365, 30)
max_dte = st.number_input("Max DTE", 1, 365, 60)
min_delta = st.number_input("Min Delta", -1.0, 1.0, -0.30, step=0.01)
max_delta = st.number_input("Max Delta", -1.0, 1.0, 0.30, step=0.01)
use_abs_delta = st.checkbox("Use Absolute Delta (ignore sign)?", True)

if st.button("Get Options Chain"):
    with st.spinner(f"Fetching contracts for {symbol} expiring between {min_dte} and {max_dte} days..."):
        contracts = fetch_options_contracts(symbol, min_dte, max_dte, min_delta, max_delta, use_abs_delta)

    if contracts:
        df = pd.DataFrame(contracts)
        st.success(f"Total contracts pulled: {len(df)}")
        st.dataframe(df)
    else:
        st.warning("No contracts matched your filters.")
