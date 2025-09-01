import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Options Strategy Analyzer", layout="wide")

API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Strategy Analyzer")

# ---------------- SYMBOL INPUT ----------------
default_symbols = ["SPX", "XSP", "TQQQ", "QQQ", "PLTR", "SOXL", "AAPL", "TSLA"]
ticker = st.selectbox("Select Symbol", default_symbols, index=0)
custom_symbol = st.text_input("Or type a custom symbol", "")
if custom_symbol.strip():
    ticker = custom_symbol.strip().upper()

# ---------------- FETCH EXPIRATIONS ----------------
expiries = []
expiry_filter = None
if ticker:
    exp_url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&apiKey={API_KEY}&limit=1000"
    response = requests.get(exp_url)
    if response.status_code == 200:
        exp_data = response.json()
        if "results" in exp_data:
            expiries = sorted(set([opt["expiration_date"] for opt in exp_data["results"]]))
            if expiries:
                # Default DTE ~ 45
                expiry_filter = st.selectbox("Expiration (DTE)", expiries, 
                                             index=min(len(expiries)-1, expiries.index(min(expiries, key=lambda x: abs((pd.to_datetime(x)-pd.Timestamp.today()).days-45)))))
            else:
                st.warning("No expirations found.")
    else:
        st.error("Failed to fetch expirations.")

# ---------------- DELTA RANGE ----------------
col1, col2 = st.columns(2)
with col1:
    min_delta = st.number_input("Min Delta", value=5)
with col2:
    max_delta = st.number_input("Max Delta", value=35)

# ---------------- FETCH OPTION CHAIN ----------------
if st.button("Get Option Chain") and expiry_filter:
    with st.spinner("Fetching option chain..."):
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}&limit=1000"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                df = pd.DataFrame([
                    {
                        "Contract": opt["details"]["ticker"],
                        "Type": opt["details"]["contract_type"],
                        "Strike": opt["details"]["strike_price"],
                        "Expiration": opt["details"]["expiration_date"],
                        "Delta": abs(opt.get("greeks", {}).get("delta", 0)),
                        "Gamma": opt.get("greeks", {}).get("gamma"),
                        "Theta": opt.get("greeks", {}).get("theta"),
                        "Vega": opt.get("greeks", {}).get("vega"),
                        "IV": opt.get("implied_volatility"),
                        "Last Price": opt["day"].get("close"),
                    }
                    for opt in data["results"]
                    if opt["details"]["expiration_date"] == expiry_filter
                ])

                # Apply delta filter
                df = df[(df["Delta"]*100 >= min_delta) & (df["Delta"]*100 <= max_delta)]

                # Split calls and puts
                calls = df[df["Type"] == "call"].set_index("Strike")
                puts = df[df["Type"] == "put"].set_index("Strike")

                # Align side by side
                merged = pd.concat([calls, puts], axis=1, keys=["Call", "Put"])

                st.subheader(f"📋 Options Chain for {ticker} - {expiry_filter}")
                st.dataframe(merged, use_container_width=True)

                # Download CSV
                csv = merged.to_csv().encode("utf-8")
                st.download_button("Download CSV", csv, f"{ticker}_options_chain.csv", "text/csv")

            else:
                st.error("No options data available.")
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
