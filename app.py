import streamlit as st
import pandas as pd
import requests
import asyncio
import aiohttp

# 🔑 Your Polygon.io API Key
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.set_page_config(page_title="Options Analyzer", layout="wide")

# ---------------------------
# Async fetch for snapshotsimport streamlit as st
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
# Function: Fetch All Options
# -------------------------------
def fetch_all_options(symbol, api_key, per_page=250):
    all_results = []
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={api_key}&limit={per_page}"
    while url:
        resp = requests.get(url)
        if resp.status_code != 200:
            st.error(f"API Error {resp.status_code}: {resp.text}")
            return pd.DataFrame()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        # Polygon doesn’t always provide "next_url"
        url = data.get("next_url")
        if url:
            url += f"&apiKey={api_key}"
    return pd.DataFrame(all_results)


# -------------------------------
# Data Fetch
# -------------------------------
if st.button("Fetch Options Data"):
    with st.spinner("Fetching data..."):
        raw_df = fetch_all_options(ticker, API_KEY)

        if not raw_df.empty:
            # Normalize clean DataFrame
            df = pd.DataFrame([
                {
                    "Contract": opt.get("details", {}).get("ticker"),
                    "Type": opt.get("details", {}).get("contract_type"),
                    "Strike": opt.get("details", {}).get("strike_price"),
                    "Expiration": opt.get("details", {}).get("expiration_date"),
                    "Delta": opt.get("greeks", {}).get("delta"),
                    "Gamma": opt.get("greeks", {}).get("gamma"),
                    "Theta": opt.get("greeks", {}).get("theta"),
                    "Vega": opt.get("greeks", {}).get("vega"),
                    "IV": opt.get("implied_volatility"),
                    "OI": opt.get("open_interest"),
                    "Last Price": opt.get("day", {}).get("close"),
                    "Volume": opt.get("day", {}).get("volume"),
                }
                for opt in raw_df.to_dict(orient="records")
            ])
            st.session_state["options_df"] = df
        else:
            st.warning(f"No options data available for {ticker}. Try another symbol.")


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
        if min_val == max_val:
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
    if filtered.empty:
        st.warning("No contracts match your filter settings.")
    else:
        st.dataframe(filtered, use_container_width=True)

        # Download CSV
        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{ticker}_options.csv",
            mime="text/csv"
        )

        # -------------------------------
        # Visualization
        # -------------------------------
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

            if pcr_oi is not None:
                if pcr_oi < 0.7:
                    st.success("📈 Bullish Bias → Consider *Bull Call Spread / Short Puts*")
                elif 0.7 <= pcr_oi <= 1.3:
                    st.info("⚖ Neutral Bias → Consider *Iron Condor / Straddle*")
                else:
                    st.error("📉 Bearish Bias → Consider *Bear Put Spread / Short Calls*")
            else:
                st.warning("⚠ PCR could not be calculated (missing OI data).")

        strategy_section(filtered)
# ---------------------------
async def fetch_snapshot(session, url):
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None
    except:
        return None

async def fetch_snapshots(contracts, progress):
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for contract in contracts:
            url = f"https://api.polygon.io/v3/snapshot/options/{contract}?apiKey={API_KEY}"
            tasks.append(fetch_snapshot(session, url))
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            if result:
                results.append(result)
            progress.progress((i+1)/len(tasks))
    return results

# ---------------------------
# Fetch Options Contracts
# ---------------------------
def get_options_chain(symbol):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={symbol}&limit=1000&apiKey={API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        return pd.DataFrame()
    data = r.json().get("results", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    return df

# ---------------------------
# Streamlit UI
# ---------------------------
st.title("📊 Options Analyzer")

symbol = st.text_input("Enter Stock Ticker (e.g. AAPL, TSLA, SPX)", "")

if st.button("Fetch Options Data"):
    if not symbol:
        st.error("Please enter a stock ticker")
    else:
        with st.spinner("Fetching contracts..."):
            df = get_options_chain(symbol.upper())

        if df.empty:
            st.error(f"No options chain available for symbol '{symbol.upper()}'. Try another.")
        else:
            st.success(f"Found {len(df)} contracts for {symbol.upper()}")

            # UI Filters
            expirations = ["All"] + sorted(df["expiration_date"].dropna().unique().tolist())
            exp_filter = st.selectbox("Expiration", expirations)
            types = ["All", "call", "put"]
            type_filter = st.selectbox("Type", types)

            min_strike, max_strike = st.slider(
                "Strike Range",
                min_value=int(df["strike_price"].min()),
                max_value=int(df["strike_price"].max()),
                value=(int(df["strike_price"].min()), int(df["strike_price"].max())),
                step=1
            )

            # Apply filters
            fdf = df.copy()
            if exp_filter != "All":
                fdf = fdf[fdf["expiration_date"] == exp_filter]
            if type_filter != "All":
                fdf = fdf[fdf["type"] == type_filter]
            fdf = fdf[(fdf["strike_price"] >= min_strike) & (fdf["strike_price"] <= max_strike)]

            if fdf.empty:
                st.warning("No contracts match your filters.")
            else:
                st.write(f"Fetching snapshot data for {len(fdf)} contracts...")

                # Progress bar
                progress = st.progress(0)

                # Fetch snapshots
                contracts = fdf["ticker"].tolist()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                snapshots = loop.run_until_complete(fetch_snapshots(contracts, progress))

                # Merge snapshot data
                rows = []
                for snap in snapshots:
                    try:
                        data = snap.get("results", {})
                        if not data:
                            continue
                        rows.append({
                            "Contract": data.get("details", {}).get("ticker"),
                            "Type": data.get("details", {}).get("contract_type"),
                            "Strike": data.get("details", {}).get("strike_price"),
                            "Expiration": data.get("details", {}).get("expiration_date"),
                            "Delta": data.get("greeks", {}).get("delta"),
                            "Gamma": data.get("greeks", {}).get("gamma"),
                            "Theta": data.get("greeks", {}).get("theta"),
                            "Vega": data.get("greeks", {}).get("vega"),
                            "IV": data.get("implied_volatility"),
                            "OI": data.get("open_interest"),
                            "Last Price": data.get("last_quote", {}).get("bid") or data.get("last_quote", {}).get("ask"),
                            "Volume": data.get("day", {}).get("volume")
                        })
                    except:
                        continue

                if rows:
                    outdf = pd.DataFrame(rows)
                    st.subheader("📑 Filtered Options Chain")
                    st.dataframe(outdf, use_container_width=True)

                    # Download button
                    csv = outdf.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"{symbol.upper()}_options_chain.csv",
                        mime="text/csv"
                    )
                else:
                    st.error("No snapshot data could be fetched for these contracts.")
