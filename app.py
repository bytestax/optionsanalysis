import streamlit as st
import requests
import pandas as pd

# ----------------------------
# App Config
# ----------------------------
st.set_page_config(page_title="Options Analyzer", layout="wide")
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.title("📊 Options Analyzer")

# ----------------------------
# Input Ticker
# ----------------------------
ticker = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "AAPL").upper()

# ----------------------------
# Fetch Data
# ----------------------------
if st.button("Fetch Options Data"):
    progress = st.progress(0, text="Fetching data...")

    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}&limit=250"
    try:
        response = requests.get(url, timeout=30)
        progress.progress(30, text="Parsing response...")

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

                # Drop rows where nothing is populated
                df = df.dropna(how="all")

                # Replace NaN with 0 for numeric stability
                num_cols = ["Delta", "Gamma", "Theta", "Vega", "IV", "OI", "Last Price", "Volume"]
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

                st.session_state["options_df"] = df
                st.success("✅ Data fetched successfully!")
            else:
                st.error("No options data available for this ticker.")
        else:
            st.error(f"API Error {response.status_code}: {response.text}")

    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")

    progress.progress(100, text="Done!")

# ----------------------------
# Filters & Display
# ----------------------------
if "options_df" in st.session_state and not st.session_state["options_df"].empty:
    df = st.session_state["options_df"]

    st.subheader("🔎 Filter Options")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        expiries = sorted(df["Expiration"].dropna().unique().tolist())
        expiry_filter = st.selectbox("Expiration", ["All"] + expiries)

    with col2:
        type_filter = st.selectbox("Type", ["All", "call", "put"])

    with col3:
        min_strike, max_strike = float(df["Strike"].min()), float(df["Strike"].max())
        strike_range = st.slider("Strike Range", min_strike, max_strike, (min_strike, max_strike))

    with col4:
        # Defensive defaults for Delta
        min_delta, max_delta = float(df["Delta"].min()), float(df["Delta"].max())
        if min_delta == max_delta:
            min_delta, max_delta = -1.0, 1.0
        delta_range = st.slider("Delta Range", min_delta, max_delta, (min_delta, max_delta))

    # Apply filters
    filtered = df.copy()
    if expiry_filter != "All":
        filtered = filtered[filtered["Expiration"] == expiry_filter]
    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]
    filtered = filtered[(filtered["Strike"] >= strike_range[0]) & (filtered["Strike"] <= strike_range[1])]
    filtered = filtered[(filtered["Delta"] >= delta_range[0]) & (filtered["Delta"] <= delta_range[1])]

    # Show results
    st.subheader("📋 Filtered Options Chain")
    st.dataframe(filtered, use_container_width=True)

    # Download CSV
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name="options_data.csv", mime="text/csv")

    # Visualization
    if not filtered.empty:
        st.subheader("📈 Greeks Visualization")
        st.scatter_chart(
            filtered,
            x="Strike",
            y=["Delta", "Gamma", "Theta", "Vega"]
        )

# ----------------------------
# SPX special note
# ----------------------------
if ticker == "SPX":
    st.warning("⚠️ SPX options data may be incomplete (missing greeks or volumes).")
