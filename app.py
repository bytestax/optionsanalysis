import os
import requests
import streamlit as st
import pandas as pd

# -------------------------------
# Load API key
# -------------------------------
API_KEY = "GuHtoE7JtmzxOpLU_yL_RQOnF1Leliqw"

BASE_URL = "https://api.polygon.io"

# -------------------------------
# Fetch options chain with Greeks
# -------------------------------
def fetch_options_chain(symbol):
    url = f"{BASE_URL}/v3/snapshot/options/{symbol}?greeks=true&apiKey={API_KEY}"
    resp = requests.get(url)

    if resp.status_code != 200:
        st.error(f"Error fetching options: {resp.status_code} - {resp.text}")
        return []

    data = resp.json()
    return data.get("results", {}).get("options", [])

# -------------------------------
# Convert API response → DataFrame
# -------------------------------
def process_options_data(options):
    rows = []
    for opt in options:
        details = opt.get("details", {})
        last_quote = opt.get("last_quote", {})
        last_trade = opt.get("last_trade", {})
        greeks = opt.get("greeks", {})

        rows.append({
            "Symbol": details.get("ticker", ""),
            "Expiration": details.get("expiration_date", ""),
            "Strike": details.get("strike_price", ""),
            "Type": details.get("contract_type", ""),
            "Bid": last_quote.get("bid", ""),
            "Ask": last_quote.get("ask", ""),
            "Last Price": last_trade.get("price", ""),
            "Implied Vol": greeks.get("iv", None),
            "Delta": greeks.get("delta", None),
            "Gamma": greeks.get("gamma", None),
            "Theta": greeks.get("theta", None),
            "Vega": greeks.get("vega", None),
            "Open Interest": opt.get("open_interest", ""),
            "Volume": opt.get("day", {}).get("volume", "")
        })
    return pd.DataFrame(rows)

# -------------------------------
# Streamlit App
# -------------------------------
st.title("📈 Options Chain with Greeks")

symbol = st.text_input("Enter ticker symbol", value="AAPL").upper()

if st.button("Fetch Options Data"):
    options = fetch_options_chain(symbol)

    if not options:
        st.warning("No options data returned. Check ticker symbol or market hours.")
    else:
        # Check if greeks are missing in all contracts
        if all(not opt.get("greeks") for opt in options):
            st.warning("⚠️ No Greeks returned — please confirm your API key is tied to your paid plan and that the market is open.")

        df = process_options_data(options)
        st.dataframe(df)

        # Allow CSV download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{symbol}_options.csv",
            mime="text/csv",
        )
