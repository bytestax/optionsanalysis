import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time

st.set_page_config(page_title="Options Analyzer", layout="wide")

API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Analyzer")

# Input ticker
ticker = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "AAPL")

# Fetch button
if st.button("Fetch Options Data"):
    progress = st.progress(0, text="Initializing fetch...")

    with st.spinner("Fetching options data..."):
        try:
            url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}&limit=250"
            response = requests.get(url)
            progress.progress(25, text="Contacting Polygon API...")

            if response.status_code == 200:
                data = response.json()
                progress.progress(50, text="Processing data...")

                if "results" in data and data["results"]:
                    df = pd.DataFrame([
                        {
                            "Contract": opt["details"]["ticker"],
                            "Type": opt["details"]["contract_type"],
                            "Strike": opt["details"]["strike_price"],
                            "Expiration": opt["details"]["expiration_date"],
                            "Delta": opt.get("greeks", {}).get("delta"),
                            "Gamma": opt.get("greeks", {}).get("gamma"),
                            "Theta": opt.get("greeks", {}).get("theta"),
                            "Vega": opt.get("greeks", {}).get("vega"),
                            "IV": opt.get("implied_volatility"),
                            "OI": opt.get("open_interest"),
                            "Last Price": opt["day"].get("close") if "day" in opt else None,
                            "Volume": opt["day"].get("volume") if "day" in opt else None,
                        }
                        for opt in data["results"]
                    ])
                    st.session_state["options_df"] = df
                    progress.progress(100, text="Data loaded successfully ✅")
                else:
                    st.error(f"❌ No options chain available for symbol '{ticker.upper()}'. Try another.")
                    progress.empty()
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
                progress.empty()

        except Exception as e:
            st.error(f"⚠️ Failed to fetch data: {e}")
            progress.empty()

# Filtering & visualization
if "options_df" in st.session_state and not st.session_state["options_df"].empty:
    df = st.session_state["options_df"]

    st.subheader("🔎 Filter Options")

    # Filters on top bar
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        expiries = df["Expiration"].dropna().unique()
        expiry_filter = st.selectbox("Expiration", ["All"] + sorted(expiries.tolist()))

    with col2:
        type_filter = st.selectbox("Type", ["All", "call", "put"])

    with col3:
        min_strike, max_strike = st.slider("Strike Range",
                                           float(df["Strike"].min(skipna=True)),
                                           float(df["Strike"].max(skipna=True)),
                                           (float(df["Strike"].min(skipna=True)),
                                            float(df["Strike"].max(skipna=True))))

    with col4:
        # Handle NaN safely
        if df["Delta"].dropna().empty:
            min_delta, max_delta = -1, 1
        else:
            min_delta, max_delta = st.slider("Delta Range",
                                             float(df["Delta"].min(skipna=True)),
                                             float(df["Delta"].max(skipna=True)),
                                             (float(df["Delta"].min(skipna=True)),
                                              float(df["Delta"].max(skipna=True))))

    # Apply filters
    filtered = df.copy()

    if expiry_filter != "All":
        filtered = filtered[filtered["Expiration"] == expiry_filter]

    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]

    filtered = filtered[(filtered["Strike"] >= min_strike) & (filtered["Strike"] <= max_strike)]

    if "Delta" in filtered and not filtered["Delta"].dropna().empty:
        filtered = filtered[(filtered["Delta"] >= min_delta) & (filtered["Delta"] <= max_delta)]

    # Show results
    st.subheader("📋 Filtered Options Chain")
    st.dataframe(filtered, use_container_width=True)

    # Download CSV
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"{ticker.upper()}_options.csv",
        mime="text/csv"
    )

    # Visualization
    if not filtered.empty:
        st.subheader("📈 Greeks Visualization")

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(filtered["Strike"], filtered["Delta"], label="Delta", color="blue", alpha=0.6)
        ax.scatter(filtered["Strike"], filtered["Gamma"], label="Gamma", color="red", alpha=0.6)
        ax.scatter(filtered["Strike"], filtered["Theta"], label="Theta", color="green", alpha=0.6)
        ax.scatter(filtered["Strike"], filtered["Vega"], label="Vega", color="orange", alpha=0.6)

        ax.set_xlabel("Strike Price")
        ax.set_ylabel("Value")
        ax.legend()
        st.pyplot(fig)
