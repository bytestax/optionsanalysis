import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Options Analyzer", page_icon="📊", layout="wide")
st.title("📊 Options Analyzer with Greeks & Advanced Filters")

# User input
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL):", "AAPL")

# 🔑 API Key
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
        # 🔀 Toggle between Raw and Cleaned
        view_mode = st.radio("View Mode", ["Cleaned Data", "Raw Data"], horizontal=True)

        if view_mode == "Raw Data":
            st.subheader("Raw API Data")
            st.json(results)  # show unfiltered API JSON

        else:
            df = pd.DataFrame([{
                "Strike": opt["details"].get("strike_price"),
                "Expiry": opt["details"].get("expiration_date"),
                "Type": opt["details"].get("contract_type"),
                "Delta": (opt.get("greeks") or {}).get("delta"),
                "Gamma": (opt.get("greeks") or {}).get("gamma"),
                "Theta": (opt.get("greeks") or {}).get("theta"),
                "Vega": (opt.get("greeks") or {}).get("vega"),
                "Implied Volatility": opt.get("implied_volatility"),
                "Last Price": (opt.get("day") or {}).get("close")
            } for opt in results])

            # Keep full dataset before filters
            full_df = df.copy()

            # 🎯 Sidebar filters
            st.sidebar.header("Filters")

            expiry_filter = st.sidebar.multiselect("Select Expiry", sorted(full_df["Expiry"].dropna().unique()))
            type_filter = st.sidebar.multiselect("Select Option Type", sorted(full_df["Type"].dropna().unique()))

            if not full_df["Strike"].dropna().empty:
                min_strike, max_strike = float(full_df["Strike"].min()), float(full_df["Strike"].max())
                strike_range = st.sidebar.slider("Select Strike Range", min_strike, max_strike, (min_strike, max_strike))

            if not full_df["Delta"].dropna().empty:
                delta_range = st.sidebar.slider("Select Delta Range", -1.0, 1.0, (-1.0, 1.0))

            if not full_df["Theta"].dropna().empty:
                theta_min, theta_max = float(full_df["Theta"].min()), float(full_df["Theta"].max())
                theta_range = st.sidebar.slider("Select Theta Range", theta_min, theta_max, (theta_min, theta_max))

            if not full_df["Implied Volatility"].dropna().empty:
                iv_min, iv_max = float(full_df["Implied Volatility"].min()), float(full_df["Implied Volatility"].max())
                iv_range = st.sidebar.slider("Select IV Range", iv_min, iv_max, (iv_min, iv_max))

            # Apply filters
            df = full_df.copy()
            if expiry_filter:
                df = df[df["Expiry"].isin(expiry_filter)]
            if type_filter:
                df = df[df["Type"].isin(type_filter)]
            if "strike_range" in locals():
                df = df[(df["Strike"] >= strike_range[0]) & (df["Strike"] <= strike_range[1])]
            if "delta_range" in locals():
                df = df[(df["Delta"].fillna(0) >= delta_range[0]) & (df["Delta"].fillna(0) <= delta_range[1])]
            if "theta_range" in locals():
                df = df[(df["Theta"].fillna(0) >= theta_range[0]) & (df["Theta"].fillna(0) <= theta_range[1])]
            if "iv_range" in locals():
                df = df[(df["Implied Volatility"].fillna(0) >= iv_range[0]) & (df["Implied Volatility"].fillna(0) <= iv_range[1])]

            # Show Data
            st.subheader("Options Data")
            st.dataframe(df if not df.empty else full_df)

            # Charts
            if not df.empty:
                st.subheader("Delta vs Strike")
                st.scatter_chart(df, x="Strike", y="Delta")

                st.subheader("Average IV vs Expiry")
                iv_by_expiry = df.groupby("Expiry")["Implied Volatility"].mean().reset_index()
                st.line_chart(iv_by_expiry, x="Expiry", y="Implied Volatility")

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "options_data.csv", "
