import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Options Analyzer", page_icon="📊", layout="wide")
st.title("📊 Options Analyzer with Greeks")

# User input
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL):", "AAPL")

# 🔑 Fixed API Key
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

# Function to fetch paginated options data
def fetch_options_data(ticker, api_key):
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?limit=100&apiKey={api_key}"
    results = []
    page = 0

    # Progress bar
    progress = st.progress(0.0)

    while url:
        page += 1
        resp = requests.get(url)
        data = resp.json()

        if "results" in data:
            results.extend(data["results"])
        else:
            break

        url = data.get("next_url")
        if url:
            url += f"&apiKey={api_key}"

        # Update progress bar (simulate progress up to 10 pages)
        progress.progress(min(page / 10, 1.0))

    progress.progress(1.0)
    return results

if st.button("Fetch Options Data"):
    results = fetch_options_data(ticker, API_KEY)

    if results:
        df = pd.DataFrame([{
            "Strike": opt["details"]["strike_price"],
            "Expiry": opt["details"]["expiration_date"],
            "Type": opt["details"]["contract_type"],
            "Delta": opt.get("greeks", {}).get("delta"),
            "Gamma": opt.get("greeks", {}).get("gamma"),
            "Theta": opt.get("greeks", {}).get("theta"),
            "Vega": opt.get("greeks", {}).get("vega"),
            "Implied Volatility": opt.get("implied_volatility"),
            "Last Price": opt.get("day", {}).get("close")
        } for opt in results])

        # Show table
        st.subheader("Options Data")
        st.dataframe(df)

        # Charts
        if not df.empty:
            st.subheader("Delta vs Strike")
            st.scatter_chart(df, x="Strike", y="Delta")

            st.subheader("Average IV vs Expiry")
            iv_by_expiry = df.groupby("Expiry")["Implied Volatility"].mean().reset_index()
            st.line_chart(iv_by_expiry, x="Expiry", y="Implied Volatility")

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "options_data.csv", "text/csv")
    else:
        st.error("No data found. Please check the ticker or API key.")
