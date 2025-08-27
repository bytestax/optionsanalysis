import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
API_KEY = "D2ss7P80Pm42ShCqcexGaZUD59IaKR9M"
BASE_URL = "https://api.polygon.io"

# ---------------------------
# FETCH OPTION CHAIN CONTRACTS
# ---------------------------
def fetch_option_contracts(symbol):
    url = f"{BASE_URL}/v3/reference/options/contracts?underlying_ticker={symbol}&limit=1000&apiKey={API_KEY}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json().get("results", [])

# ---------------------------
# FETCH SNAPSHOT WITH GREEKS
# ---------------------------
def fetch_greeks(symbol, option_symbol):
    url = f"{BASE_URL}/v3/snapshot/options/{symbol}/{option_symbol}?apiKey={API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json().get("results", {})
        if data:
            return {
                "symbol": option_symbol,
                "type": data.get("details", {}).get("contract_type"),
                "strike": data.get("details", {}).get("strike_price"),
                "expiration": data.get("details", {}).get("expiration_date"),
                "delta": data.get("greeks", {}).get("delta"),
                "gamma": data.get("greeks", {}).get("gamma"),
                "theta": data.get("greeks", {}).get("theta"),
                "vega": data.get("greeks", {}).get("vega"),
                "iv": data.get("iv"),
                "bid": data.get("last_quote", {}).get("bid"),
                "ask": data.get("last_quote", {}).get("ask"),
                "last_price": data.get("last_trade", {}).get("price"),
            }
    return None

# ---------------------------
# STREAMLIT APP
# ---------------------------
st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📈 Options Analyzer with Greeks (Polygon.io)")

symbol = st.text_input("Enter Symbol:", "SPY")
min_dte = st.number_input("Min DTE", min_value=0, value=30)
max_dte = st.number_input("Max DTE", min_value=1, value=60)
min_delta = st.number_input("Min Delta", -1.0, 1.0, -0.30, 0.01)
max_delta = st.number_input("Max Delta", -1.0, 1.0, 0.57, 0.01)

if st.button("Fetch Options"):
    st.info("Fetching option contracts...")
    contracts = fetch_option_contracts(symbol)

    rows = []
    today = datetime.today().date()

    for contract in contracts:
        expiration = datetime.strptime(contract["expiration_date"], "%Y-%m-%d").date()
        dte = (expiration - today).days
        if dte < min_dte or dte > max_dte:
            continue

        option_symbol = contract["ticker"]
        greeks_data = fetch_greeks(symbol, option_symbol)

        if greeks_data and greeks_data["delta"] is not None:
            if min_delta <= greeks_data["delta"] <= max_delta:
                greeks_data["dte"] = dte
                rows.append(greeks_data)

    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values(by=["expiration", "type", "strike"])
        st.success(f"Found {len(df)} matching option contracts ✅")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("⚠️ No options matched your filters.")
