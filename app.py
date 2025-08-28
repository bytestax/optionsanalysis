import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Polygon API Key
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

# Suggested tickers
suggested_tickers = ["SPY", "QQQ", "AAPL", "TSLA", "SOXL", "NVDA", "MSFT", "AMD", "PLTR", "XSP"]

# Page setup
st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📊 Options Analyzer with Greeks")

# --- Inputs ---
st.subheader("Choose a Ticker")
ticker_choice = st.selectbox("Pick a ticker from the list:", suggested_tickers)
custom_symbol = st.text_input("Or enter a custom symbol:", "").upper()
symbol = custom_symbol if custom_symbol else ticker_choice

col1, col2, col3, col4 = st.columns(4)
with col1:
    min_dte = st.number_input("Min DTE", value=0, min_value=0)
with col2:
    max_dte = st.number_input("Max DTE", value=90, min_value=1)
with col3:
    min_delta = st.number_input("Min Delta", value=-1.0, min_value=-1.0, max_value=1.0)
with col4:
    max_delta = st.number_input("Max Delta", value=1.0, min_value=-1.0, max_value=1.0)

# Helper function to fetch all pages from Polygon
def fetch_all_options(symbol):
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
    all_results = []

    while url:
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"⚠️ API Error {response.status_code}: {response.text}")
            return []

        data = response.json()
        if "results" in data and data["results"]:
            all_results.extend(data["results"])
        else:
            break

        # handle pagination safely
        url = data.get("next_url")
        if url:
            if "apiKey" not in url:
                url += f"&apiKey={API_KEY}"
        else:
            break

    return all_results

# --- Fetch Options ---
if st.button("Fetch Options"):
    with st.spinner("⏳ Fetching options data from Polygon..."):
        raw_results = fetch_all_options(symbol)

    if not raw_results:
        st.warning(f"⚠️ No options available for {symbol}.")
        st.info(f"💡 Try one of these tickers instead: {', '.join(suggested_tickers)}")
    else:
        options_data = []
        for opt in raw_results:
            try:
                details = opt["details"]
                greeks = opt.get("greeks", {})
                expire_date = datetime.strptime(details["expiration_date"], "%Y-%m-%d").date()
                dte = (expire_date - datetime.today().date()).days

                # Filter DTE
                if not (min_dte <= dte <= max_dte):
                    continue

                # Filter Delta
                delta = greeks.get("delta")
                if delta is None or not (min_delta <= float(delta) <= max_delta):
                    continue

                options_data.append({
                    "Symbol": details.get("ticker"),
                    "Type": details.get("contract_type"),
                    "Strike": details.get("strike_price"),
                    "Expiry": details.get("expiration_date"),
                    "DTE": dte,
                    "Delta": round(float(greeks.get("delta", 0)), 3),
                    "Gamma": round(float(greeks.get("gamma", 0)), 3),
                    "Theta": round(float(greeks.get("theta", 0)), 3),
                    "Vega": round(float(greeks.get("vega", 0)), 3),
                    "Underlying Price": details.get("underlying_price")
                })
            except Exception:
                continue

        # Display results
        if options_data:
            df = pd.DataFrame(options_data)
            df = df.sort_values(by=["Expiry", "Strike"]).reset_index(drop=True)
            st.success(f"✅ Found {len(df)} matching options for {symbol}")
            st.dataframe(df)
        else:
            st.warning(f"⚠️ No options found for {symbol} with the given filters.")
            st.info(f"💡 Try adjusting DTE or Delta range.")
