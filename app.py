import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time

# -------------------------------
# App Config
# -------------------------------
st.set_page_config(page_title="Options Analyzer", layout="wide")
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Analyzer")

# -------------------------------
# Function: Fetch All Options (with caching)
# -------------------------------
@st.cache_data(ttl=300)  # cache results for 5 minutes
def fetch_all_options(symbol, api_key, per_page=250):
    all_results = []
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={api_key}&limit={per_page}"
    while url:
        resp = requests.get(url)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        # Polygon doesn’t always provide "next_url"
        url = data.get("next_url")
        if url:
            url += f"&apiKey={api_key}"
    return pd.DataFrame(all_results)


# -------------------------------
# Input Section
# -------------------------------
ticker = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "AAPL")

if st.button("Fetch Options Data"):
    progress = st.progress(0)
    with st.spinner("Fetching data..."):
        # Fake progress while API loads
        for i in range(50):
            time.sleep(0.01)
            progress.progress(i + 1)
        raw_df = fetch_all_options(ticker, API_KEY)
        for i in range(50, 100):
            time.sleep(0.01)
            progress.progress(i + 1)

        if not raw_df.empty:
            df = pd.DataFrame([
                {
                    "Contract": opt.get("details", {}).get("ticker"),
                    "Type": opt.get("details", {}).get("contract_type"),
                    "Strike": opt.get("details", {}).get("strike_price"),
                    "Expiration": opt.get("details", {}).get("expiration_date"),
                    "Delta": opt.get("greeks", {}).get("delta"),
                    "Gamma": opt.get("greeks", {}).get("gamma"),
                    "Theta": opt.get("greeks", {}).get("theta"),
                    "Vega": opt.get("greeks", {}).get("vega"),
                    "IV": opt.get("implied_volatility"),
                    "OI": opt.get("open_interest"),
                    "Last Price": opt.get("day", {}).get("close"),
                    "Volume": opt.get("day", {}).get("volume"),
                }
                for opt in raw_df.to_dict(orient="records")
            ])
            st.session_state["options_df"] = df
            progress.empty()
        else:
            st.warning(f"No options data available for {ticker}. Try another symbol.")
            progress.empty()
