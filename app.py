import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# Polygon API Key
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

# Suggested tickers
suggested_tickers = ["SPY", "QQQ", "AAPL", "TSLA", "SOXL", "NVDA", "MSFT", "AMD","PLTR", "XSP"]

st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📊 Options Analyzer")

# Dropdown + custom ticker
st.subheader("Choose a Ticker")
ticker_choice = st.selectbox("Pick a ticker from the list:", suggested_tickers)
custom_symbol = st.text_input("Or enter a custom symbol:", "").upper()

# Final symbol priority → custom input > dropdown
symbol = custom_symbol if custom_symbol else ticker_choice

# User inputs
min_dte = st.number_input("Min DTE", value=10)
max_dte = st.number_input("Max DTE", value=60)
min_delta = st.number_input("Min Delta", value=-0.30)
max_delta = st.number_input("Max Delta", value=0.70)

if st.button("Fetch Options"):
    base_url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?limit=100&apiKey={API_KEY}"
    next_url = base_url
    options_data = []

    progress = st.progress(0)
    page = 0

    while next_url:
        response = requests.get(next_url)
        if response.status_code != 200:
            st.error(f"⚠️ API Error {response.status_code}: {response.text}")
            break

        data = response.json()
        results = data.get("results", [])

        for opt in results:
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
                            "IV": round(opt.get("implied_volatility", 0), 3),
                            "Underlying Price": opt["underlying_asset"].get("ticker")
                        })
            except Exception:
                continue

        page += 1
        progress.progress(min(page * 10, 100))

        # Pagination
        next_url = data.get("next_url")
        if next_url:
            if "apiKey" not in next_url:
                next_url += f"&apiKey={API_KEY}"

    if options_data:
        df = pd.DataFrame(options_data)
        st.dataframe(df)

        # ---- PLOTS ----
        st.subheader("📈 Visualizations")

        # Delta vs Strike
        fig1, ax1 = plt.subplots()
        ax1.scatter(df["Strike"], df["Delta"], alpha=0.7)
        ax1.set_xlabel("Strike Price")
        ax1.set_ylabel("Delta")
        ax1.set_title("Delta vs Strike")
        st.pyplot(fig1)

        # IV vs Expiry
        fig2, ax2 = plt.subplots()
        df_grouped = df.groupby("Expiry")["IV"].mean().reset_index()
        ax2.plot(df_grouped["Expiry"], df_grouped["IV"], marker="o")
        ax2.set_xlabel("Expiry Date")
        ax2.set_ylabel("Avg IV")
        ax2.set_title("Implied Volatility vs Expiry")
        plt.xticks(rotation=45)
        st.pyplot(fig2)

    else:
        st.warning(f"⚠️ No options found for {symbol} with the given filters.")
        st.info(f"💡 Try one of these tickers instead: {', '.join(suggested_tickers)}")
