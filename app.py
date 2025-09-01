import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------
# App Config
# -------------------------------
st.set_page_config(page_title="Options Analyzer", layout="wide")
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Analyzer")

# -------------------------------
# Input Section
# -------------------------------
ticker = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "AAPL")

# -------------------------------
# Data Fetch
# -------------------------------
if st.button("Fetch Options Data"):
    with st.spinner("Fetching data..."):
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}&limit=250"
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
                        "Delta": opt.get("greeks", {}).get("delta"),
                        "Gamma": opt.get("greeks", {}).get("gamma"),
                        "Theta": opt.get("greeks", {}).get("theta"),
                        "Vega": opt.get("greeks", {}).get("vega"),
                        "IV": opt.get("implied_volatility"),
                        "OI": opt.get("open_interest"),
                        "Last Price": opt["day"].get("close"),
                        "Volume": opt["day"].get("volume"),
                    }
                    for opt in data["results"]
                ])
                st.session_state["options_df"] = df
            else:
                st.error("No options data available for this ticker.")
        else:
            st.error(f"API Error {response.status_code}: {response.text}")

# -------------------------------
# Filters + Display
# -------------------------------
if "options_df" in st.session_state and not st.session_state["options_df"].empty:
    df = st.session_state["options_df"]

    st.subheader("🔎 Filter Options")

    # Filter Columns
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        expiries = df["Expiration"].dropna().unique()
        expiry_filter = st.selectbox("Expiration", ["All"] + sorted(expiries.tolist()))

    with col2:
        type_filter = st.selectbox("Type", ["All", "call", "put"])

    # --- Safe Sliders ---
    def safe_slider(label, series, default_padding=0.1):
        if series.dropna().empty:
            return None, None
        min_val, max_val = float(series.min()), float(series.max())
        if min_val == max_val:  # expand if flat
            min_val -= default_padding
            max_val += default_padding
        return st.slider(label, min_val, max_val, (min_val, max_val))

    with col3:
        min_strike, max_strike = safe_slider("Strike Range", df["Strike"])
    with col4:
        min_delta, max_delta = safe_slider("Delta Range", df["Delta"])
    with col5:
        min_iv, max_iv = safe_slider("IV Range", df["IV"])

    # Apply Filters
    filtered = df.copy()
    if expiry_filter != "All":
        filtered = filtered[filtered["Expiration"] == expiry_filter]
    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]
    if min_strike is not None:
        filtered = filtered[(filtered["Strike"] >= min_strike) & (filtered["Strike"] <= max_strike)]
    if min_delta is not None:
        filtered = filtered[(filtered["Delta"] >= min_delta) & (filtered["Delta"] <= max_delta)]
    if min_iv is not None:
        filtered = filtered[(filtered["IV"] >= min_iv) & (filtered["IV"] <= max_iv)]

    # -------------------------------
    # Results
    # -------------------------------
    st.subheader("📋 Filtered Options Chain")
    st.dataframe(filtered, use_container_width=True)

    # Download CSV
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="options_data.csv",
        mime="text/csv"
    )

    # -------------------------------
    # Visualization
    # -------------------------------
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

    # -------------------------------
    # Strategy (PCR)
    # -------------------------------
    def strategy_section(df):
        calls = df[df["Type"] == "call"]
        puts = df[df["Type"] == "put"]

        total_call_oi = calls["OI"].sum()
        total_put_oi = puts["OI"].sum()
        total_call_vol = calls["Volume"].sum()
        total_put_vol = puts["Volume"].sum()

        pcr_oi = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None
        pcr_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None

        st.subheader("📌 Market Strategy Insights")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Put/Call Ratio (OI)", pcr_oi if pcr_oi else "N/A")
        with col2:
            st.metric("Put/Call Ratio (Volume)", pcr_vol if pcr_vol else "N/A")

        # Strategy logic
        if pcr_oi is not None:
            if pcr_oi < 0.7:
                st.success("📈 Bullish Bias → Consider **Bull Call Spread / Short Puts**")
            elif 0.7 <= pcr_oi <= 1.3:
                st.info("⚖️ Neutral Bias → Consider **Iron Condor / Straddle**")
            else:
                st.error("📉 Bearish Bias → Consider **Bear Put Spread / Short Calls**")
        else:
            st.warning("⚠️ PCR could not be calculated (missing OI data).")

    strategy_section(filtered)
