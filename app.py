import streamlit as st
import requests
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE_URL = "https://api.polygon.io/v3"

# =========================
# HELPER FUNCTIONS
# =========================
def safe_get(data, keys, default="N/A"):
    """Safely get nested keys from dict"""
    for k in keys:
        if data is None or not isinstance(data, dict):
            return default
        data = data.get(k)
    return data if data is not None else default

def fetch_options(symbol):
    """Fetch options contracts for a symbol"""
    url = f"{BASE_URL}/reference/options/contracts?underlying_ticker={symbol}&apiKey={API_KEY}&limit=1000"
    r = requests.get(url)
    if r.status_code != 200:
        st.error(f"Error fetching options: {r.text}")
        return []
    return r.json().get("results", [])

def build_dataframe(options):
    """Convert raw options list into clean dataframe"""
    filtered_data = []
    for opt in options:
        filtered_data.append({
            "Contract": opt.get("ticker", "N/A"),
            "Type": opt.get("option_type", "N/A"),
            "Strike": opt.get("strike_price", "N/A"),
            "Expiration": opt.get("expiration_date", "N/A"),
            "Delta": safe_get(opt, ["greeks", "delta"]),
            "Gamma": safe_get(opt, ["greeks", "gamma"]),
            "Theta": safe_get(opt, ["greeks", "theta"]),
            "Vega": safe_get(opt, ["greeks", "vega"]),
            "IV": opt.get("implied_volatility", "N/A"),
            "OI": opt.get("open_interest", "N/A"),
            "Last Price": safe_get(opt, ["day", "close"]),
            "Volume": safe_get(opt, ["day", "volume"]),
        })
    return pd.DataFrame(filtered_data)

# =========================
# STREAMLIT APP
# =========================
st.set_page_config(page_title="Options Chain Viewer", layout="wide")
st.title("📊 Options Chain Viewer")

# User input
symbol = st.text_input("Enter Symbol (e.g., SPX, AAPL, TSLA)", "SPX")

if st.button("Fetch Options Chain"):
    with st.spinner("Fetching data from Polygon..."):
        options = fetch_options(symbol)

    if not options:
        st.warning("No options data found.")
    else:
        df = build_dataframe(options)

        # Sidebar filters
        exp_list = sorted(df["Expiration"].unique())
        type_list = sorted(df["Type"].unique())

        exp_filter = st.selectbox("Expiration", ["All"] + exp_list)
        type_filter = st.selectbox("Type", ["All"] + type_list)

        # Strike range filter
        min_strike, max_strike = int(df["Strike"].min()), int(df["Strike"].max())
        strike_range = st.slider("Strike Range", min_strike, max_strike, (min_strike, max_strike))

        # Apply filters
        filtered_df = df.copy()
        if exp_filter != "All":
            filtered_df = filtered_df[filtered_df["Expiration"] == exp_filter]
        if type_filter != "All":
            filtered_df = filtered_df[filtered_df["Type"] == type_filter]
        filtered_df = filtered_df[
            (filtered_df["Strike"] >= strike_range[0]) & 
            (filtered_df["Strike"] <= strike_range[1])
        ]

        # Show dataframe
        st.subheader("📋 Filtered Options Chain")
        st.dataframe(filtered_df, use_container_width=True)

        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button("Download CSV", csv, "options_chain.csv", "text/csv")
