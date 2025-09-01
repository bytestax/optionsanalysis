import streamlit as st
import pandas as pd
import requests
import asyncio
import aiohttp

# 🔑 Your Polygon.io API Key
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"

st.set_page_config(page_title="Options Analyzer", layout="wide")

# ---------------------------
# Async fetch for snapshots
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
