import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from time import sleep

# ==========================
# CONFIG
# ==========================
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE_URL = "https://api.polygon.io/v3"

# ==========================
# API HELPERS
# ==========================
def fetch_contracts(symbol):
    """Fetch option contracts for symbol"""
    url = f"{BASE_URL}/reference/options/contracts?underlying_ticker={symbol}&limit=1000&apiKey={API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        st.error(f"Contracts error: {r.text}")
        return []
    return r.json().get("results", [])

def fetch_snapshots(symbol):
    """Fetch snapshot data (with Greeks, IV, OI, price, etc.)"""
    url = f"{BASE_URL}/snapshot/options/{symbol}?apiKey={API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        st.error(f"Snapshot error: {r.text}")
        return {}
    results = r.json().get("results", [])
    # Convert list → dict keyed by contract ticker
    return {item["details"]["contract_name"]: item for item in results}

# ==========================
# DATAFRAME BUILDER
# ==========================
def build_dataframe(contracts, snapshots):
    rows = []
    for c in contracts:
        ticker = c.get("ticker")
        snap = snapshots.get(ticker, {})

        greeks = snap.get("greeks", {})
        details = snap.get("details", {})
        last_quote = snap.get("last_quote", {})
        day = snap.get("day", {})

        rows.append({
            "Contract": ticker,
            "Type": c.get("exercise_style", "N/A"),
            "Strike": c.get("strike_price", "N/A"),
            "Expiration": c.get("expiration_date", "N/A"),
            "Delta": greeks.get("delta", "N/A"),
            "Gamma": greeks.get("gamma", "N/A"),
            "Theta": greeks.get("theta", "N/A"),
            "Vega": greeks.get("vega", "N/A"),
            "IV": snap.get("implied_volatility", "N/A"),
            "OI": details.get("open_interest", "N/A"),
            "Last Price": last_quote.get("P", "N/A"),
            "Volume": day.get("volume", "N/A"),
        })
    return pd.DataFrame(rows)

# ==========================
# STREAMLIT UI
# ==========================
st.set_page_config(page_title="Options Chain", layout="wide")
st.title("📑 Filtered Options Chain")

symbol = st.text_input("Enter symbol", value="SPX")

if st.button("Fetch Data"):
    contracts = fetch_contracts(symbol)

    if not contracts:
        st.warning("No contracts found.")
    else:
        progress = st.progress(0, text="Fetching snapshot data...")
        snapshots = fetch_snapshots(symbol)
        progress.progress(100, text="Done ✅")
        sleep(0.5)

        df = build_dataframe(contracts, snapshots)

        st.dataframe(df, use_container_width=True)

        # Download option
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "options_chain.csv", "text/csv")
