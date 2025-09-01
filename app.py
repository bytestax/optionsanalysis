import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Options Analyzer", layout="wide")

API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Analyzer")

# ----------------------------
# Fetch Options Data
# ----------------------------
def fetch_options_data(ticker):
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}&limit=250"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                df = pd.DataFrame([
                    {
                        "Contract": opt.get("details", {}).get("ticker"),
                        "Type": opt.get("details", {}).get("contract_type"),
                        "Strike": opt.get("details", {}).get("strike_price"),
                        "Expiration": opt.get("details", {}).get("expiration_date"),
                        "Delta": opt.get("greeks", {}).get("delta", None),
                        "Gamma": opt.get("greeks", {}).get("gamma", None),
                        "Theta": opt.get("greeks", {}).get("theta", None),
                        "Vega": opt.get("greeks", {}).get("vega", None),
                        "IV": opt.get("implied_volatility", None),
                        "OI": opt.get("open_interest", None),
                        "Last Price": opt.get("day", {}).get("close", None),
                        "Volume": opt.get("day", {}).get("volume", None),
                    }
                    for opt in data["results"]
                ])

                # Drop completely empty rows
                df = df.dropna(how="all")

                # Fill NaNs with 0 for numeric stability
                num_cols = ["Delta", "Gamma", "Theta", "Vega", "IV", "OI", "Last Price", "Volume"]
                for col in num_cols:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

                return df
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
        return pd.DataFrame()

# ----------------------------
# Strategy Section (PCR)
# ----------------------------
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

    # PCR by expiry
    if not df.empty:
        expiry_pcr = []
        for expiry in df["Expiration"].unique():
            exp_data = df[df["Expiration"] == expiry]
            c = exp_data[exp_data["Type"] == "call"]["OI"].sum()
            p = exp_data[exp_data["Type"] == "put"]["OI"].sum()
            if c > 0:
                expiry_pcr.append((expiry, round(p / c, 2)))

        if expiry_pcr:
            exp_df = pd.DataFrame(expiry_pcr, columns=["Expiration", "PCR_OI"])
            st.subheader("📊 PCR by Expiry")
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(exp_df["Expiration"], exp_df["PCR_OI"], color="purple", alpha=0.7)
            ax.axhline(1, color="red", linestyle="--", label="Neutral (1.0)")
            ax.set_ylabel("PCR (OI)")
            ax.set_xlabel("Expiration")
            ax.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig)

# ----------------------------
# Main App
# ----------------------------
ticker = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "AAPL")

if st.button("Fetch Options Data"):
    with st.spinner("Fetching data..."):
        df = fetch_options_data(ticker)
        if not df.empty:
            st.session_state["options_df"] = df

# If data available
if "options_df" in st.session_state and not st.session_state["options_df"].empty:
    df = st.session_state["options_df"]

    st.subheader("🔎 Filter Options")

    # Filters on top bar
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        expiries = df["Expiration"].unique()
        expiry_filter = st.selectbox("Expiration", ["All"] + sorted(expiries.tolist()))

    with col2:
        type_filter = st.selectbox("Type", ["All", "call", "put"])

    with col3:
        min_strike, max_strike = st.slider("Strike Range",
                                           float(df["Strike"].min()),
                                           float(df["Strike"].max()),
                                           (float(df["Strike"].min()), float(df["Strike"].max())))

    with col4:
        min_delta, max_delta = st.slider("Delta Range",
                                         float(df["Delta"].min()),
                                         float(df["Delta"].max()),
                                         (float(df["Delta"].min()), float(df["Delta"].max())))

    # Apply filters
    filtered = df.copy()

    if expiry_filter != "All":
        filtered = filtered[filtered["Expiration"] == expiry_filter]

    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]

    filtered = filtered[(filtered["Strike"] >= min_strike) & (filtered["Strike"] <= max_strike)]
    filtered = filtered[(filtered["Delta"] >= min_delta) & (filtered["Delta"] <= max_delta)]

    # Show results
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

    # Strategy Section
    strategy_section(filtered)
