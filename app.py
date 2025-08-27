import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Polygon API Key
API_KEY = "D2ss7P80Pm42ShCqcexGaZUD59IaKR9M"

st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📊 Options Analyzer")

# User inputs
symbol = st.text_input("Enter Symbol (default: SPY)", "SPY").upper()
min_dte = st.number_input("Min DTE", value=10)
max_dte = st.number_input("Max DTE", value=60)
min_delta = st.number_input("Min Delta", value=-0.30)
max_delta = st.number_input("Max Delta", value=0.70)

if st.button("Fetch Options"):
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        st.error(f"⚠️ API Error {response.status_code}: {response.text}")
    else:
        data = response.json()

        if "results" not in data or not data["results"]:
            st.warning(f"⚠️ No options available for {symbol}. Try another ticker (e.g., SPY, AAPL, TSLA).")
        else:
            options_data = []
            for opt in data["results"]:
                try:
                    details = opt["details"]
                    greeks = opt.get("greeks", {})
                    expire_date = datetime.strptime(details["expiration_date"], "%Y-%m-%d").date()
                    dte = (expire_date - datetime.today().date()).days

                    if min_dte <= dte <= max_dte:
                        delta = greeks.get("delta")
                        if delta is not None and min_delta <= float(delta) <= max_delta:
                            options_data.append({
                                "Symbol": details.get("ticker"),
                                "Type": details.get("contract_type"),
                                "Strike": details.get("strike_price"),
                                "Expiry": details.get("expiration_date"),
                                "DTE": dte,
                                "Delta": round(float(delta), 3) if delta else None,
                                "Underlying Price": details.get("underlying_price")
                            })
                except Exception as e:
                    continue

            if options_data:
                df = pd.DataFrame(options_data)
                st.dataframe(df)
            else:
                st.warning(f"⚠️ No options found for {symbol} with the given filters.")
