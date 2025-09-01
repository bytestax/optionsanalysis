import streamlit as st
import requests
import pandas as pd

API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE_URL = "https://api.polygon.io/v3"

def safe_get(data, keys, default="N/A"):
    """Safely extract nested fields from dict"""
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k)
    return data if data is not None else default

def fetch_contracts(symbol):
    """Fetch list of option contracts (metadata only)"""
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
    return r.json().get("results", {})

def build_dataframe(contracts, snapshots):
    rows = []
    for c in contracts:
        ticker = c.get("ticker", "N/A")
        snap = snapshots.get(ticker, {})

        rows.append({
            "Contract": ticker,
            "Type": c.get("option_type", "N/A"),
            "Strike": c.get("strike_price", "N/A"),
            "Expiration": c.get("expiration_date", "N/A"),
            "Delta": safe_get(snap, ["greeks", "delta"]),
            "Gamma": safe_get(snap, ["greeks", "gamma"]),
            "Theta": safe_get(snap, ["greeks", "theta"]),
            "Vega": safe_get(snap, ["greeks", "vega"]),
            "IV": snap.get("implied_volatility", "N/A"),
            "OI": snap.get("open_interest", "N/A"),
            "Last Price": safe_get(snap, ["last_quote", "p"]),
            "Volume": snap.get("day_volume", "N/A"),
        })
    return pd.DataFrame(rows)

# =========================
# STREAMLIT APP
# =========================
st.set_page_config(page_title="Options Chain Viewer", layout="wide")
st.title("📊 Options Chain Viewer")

symbol = st.text_input("Enter Symbol (e.g., SPX, AAPL, TSLA)", "SPX")

if st.button("Fetch Options Chain"):
    with st.spinner("Fetching contracts..."):
        contracts = fetch_contracts(symbol)

    with st.spinner("Fetching live market data..."):
        snapshots = fetch_snapshots(symbol)

    if not contracts:
        st.warning("No options contracts found.")
    else:
        df = build_dataframe(contracts, snapshots)

        # Filters
        exp_filter = st.selectbox("Expiration", ["All"] + sorted(df["Expiration"].unique()))
        type_filter = st.selectbox("Type", ["All"] + sorted(df["Type"].unique()))

        min_strike, max_strike = int(df["Strike"].min()), int(df["Strike"].max())
        strike_range = st.slider("Strike Range", min_strike, max_strike, (min_strike, max_strike))

        # Apply filters
        fdf = df.copy()
        if exp_filter != "All":
            fdf = fdf[fdf["Expiration"] == exp_filter]
        if type_filter != "All":
            fdf = fdf[fdf["Type"] == type_filter]
        fdf = fdf[(fdf["Strike"] >= strike_range[0]) & (fdf["Strike"] <= strike_range[1])]

        st.subheader("📋 Filtered Options Chain")
        st.dataframe(fdf, use_container_width=True)

        csv = fdf.to_csv(index=False)
        st.download_button("Download CSV", csv, "options_chain.csv", "text/csv")
