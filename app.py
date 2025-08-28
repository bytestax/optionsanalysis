import streamlit as st
import requests
import pandas as pd

st.title("📊 Options Analyzer with Greeks")

# User input
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL):", "AAPL")

# 🔑 Fixed API Key
api_key = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

# Function to fetch paginated options data
def fetch_options_data(ticker, api_key):
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?limit=100&apiKey={api_key}"
    results = []
    page = 0

    # Progress bar
    progress = st.progress(0)
    while url:
        page += 1
        response = requests.get(url)
        data = response.json()

        if "results" in data:
            results.extend(data["results"])

        url = data.get("next_url")
        if url:
            url += f"&apiKey={api_key}"

        # update progress bar (simulate progress)
        progress.progress(min(page / 10, 1.0))

    progress.progress(1.0)
    return results

if st.button("Fetch Options Data"):
    results = fetch_options_data(ticker, api_key)

    if results:
        df = pd.DataFrame([{
            "Strike": opt["details"]["strike_price"],
            "Expiry": opt["details"]["expiration_date"],
            "Type": opt["details"]["contract_type"],
            "Delta": opt["greeks"]["delta"] if opt.get("greeks") else None,
            "Gamma": opt["greeks"]["gamma"] if opt.get("greeks") else None,
            "Theta": opt["greeks"]["theta"] if opt.get("greeks") else None,
            "Vega": opt["greeks"]["vega"] if opt.get("greeks") else None,
            "Implied Volatility": opt["implied_volatility"] if "implied_volatility" in opt else None,
            "Last Price": opt["day"]["close"] if "day" in opt else None
        } for opt in results])

        # Show table
        st.subheader("Options Data")
        st.dataframe(df)

        # Scatter chart: Delta vs Strike
        st.subheader("Delta vs Strike")
        st.scatter_chart(df, x="Strike", y="Delta")

        # Line chart: Avg IV vs Expiry
        iv_by_expiry = df.groupby("Expiry")["Implied Volatility"].mean().reset_index()
        st.subheader("Average IV vs Expiry")
        st.line_chart(iv_by_expiry, x="Expiry", y="Implied Volatility")

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "options_data.csv", "text/csv")
    else:
        st.error("No data found. Please check the ticker or API key.")
