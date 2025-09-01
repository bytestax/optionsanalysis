import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Options Strategy Analyzer", layout="wide")

st.title("📊 Options Strategy Analyzer")

# ---------------- FILTERS ----------------
col1, col2 = st.columns([2, 2])
with col1:
    symbol = st.selectbox("Select Symbol", ["AAPL", "MSFT", "TSLA", "GOOG"], index=0)
with col2:
    custom_symbol = st.text_input("Or type a custom symbol").upper()
    if custom_symbol:
        symbol = custom_symbol

expiry = st.date_input("Expiration (choose DTE)")

col3, col4 = st.columns([1, 1])
with col3:
    min_delta = st.number_input("Min Δ (abs, %)", value=10.0, step=1.0)
with col4:
    max_delta = st.number_input("Max Δ (abs, %)", value=35.0, step=1.0)

# ---------------- API BUTTON ----------------
if st.button("🔎 Get Option Chain"):
    with st.spinner("Fetching option chain..."):
        progress = st.progress(0)

        try:
            # simulate progress bar
            for i in range(1, 101, 10):
                time.sleep(0.05)
                progress.progress(i)

            # Example API request (replace with your actual API call)
            url = f"https://api.yourprovider.com/options?symbol={symbol}&expiry={expiry}"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                # Normalize JSON into dataframe safely
                df = pd.json_normalize(data.get("options", []))

                if not df.empty:
                    # Standardize column names
                    rename_map = {
                        "strike": "Strike",
                        "delta": "Delta",
                        "type": "Type",
                        "bid": "Bid",
                        "ask": "Ask",
                        "lastPrice": "Last Price"
                    }
                    df.rename(columns=rename_map, inplace=True)

                    # Apply delta filter
                    df = df[(df["Delta"].abs() * 100 >= min_delta) &
                            (df["Delta"].abs() * 100 <= max_delta)]

                    st.success(f"✅ Showing {len(df)} contracts for {symbol} expiring {expiry}")

                    st.dataframe(
                        df[["Strike", "Type", "Delta", "Bid", "Ask", "Last Price"]]
                        .sort_values("Strike"),
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.warning("No option data found for this filter.")
            else:
                st.error(f"API Error {response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"❌ Failed to fetch data: {e}")
