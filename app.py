import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Options Strategy Analyzer", layout="wide")

API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE = "https://api.polygon.io/v3"

st.title("📊 Options Strategy Analyzer")

# ---------------- SYMBOL INPUT ----------------
default_symbols = ["SPX", "XSP", "TQQQ", "QQQ", "PLTR", "SOXL", "AAPL", "TSLA"]
ticker = st.selectbox("Select Symbol", default_symbols, index=0)
custom_symbol = st.text_input("Or type a custom symbol", "")
if custom_symbol.strip():
    ticker = custom_symbol.strip().upper()

# ---------------- FETCH EXPIRATIONS ----------------
expiries = []
expiry_filter = None
if ticker:
    url = f"{BASE}/reference/options/contracts?underlying_ticker={ticker}&apiKey={API_KEY}&limit=1000"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        expiries = sorted(set([opt["expiration_date"] for opt in data.get("results", [])]))
        if expiries:
            expiry_filter = st.selectbox(
                "Expiration", expiries,
                index=min(len(expiries)-1,
                          expiries.index(min(expiries, key=lambda x: abs((pd.to_datetime(x)-pd.Timestamp.today()).days-45))))
            )
    else:
        st.error(f"Error fetching expirations: {resp.text}")

# ---------------- DELTA RANGE ----------------
col1, col2 = st.columns(2)
with col1:
    min_delta = st.number_input("Min Delta", value=5)
with col2:
    max_delta = st.number_input("Max Delta", value=35)

# ---------------- GET OPTION DATA ----------------
def fetch_option_chain(symbol, expiry):
    """Get option tickers for expiry, then fetch snapshots."""
    # Step 1: get contract tickers
    url = f"{BASE}/reference/options/contracts?underlying_ticker={symbol}&expiration_date={expiry}&apiKey={API_KEY}&limit=1000"
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Failed contracts fetch: {resp.text}")
        return []
    contracts = [c["ticker"] for c in resp.json().get("results", [])]

    # Step 2: fetch snapshots in batches of 50
    results = []
    progress = st.progress(0, text="Fetching option snapshots...")
    for i in range(0, len(contracts), 50):
        batch = contracts[i:i+50]
        url = f"{BASE}/snapshot/options_batch/{symbol}?apiKey={API_KEY}&contracts={','.join(batch)}"
        r = requests.get(url)
        if r.status_code == 200:
            snap = r.json().get("results", {})
            for c in batch:
                if c in snap:
                    results.append(snap[c])
        progress.progress((i+len(batch))/len(contracts), text=f"Fetched {i+len(batch)}/{len(contracts)}")
    progress.empty()
    return results

if st.button("Get Option Chain") and expiry_filter:
    with st.spinner("Building option chain..."):
        snaps = fetch_option_chain(ticker, expiry_filter)

        if snaps:
            today = pd.Timestamp.today().normalize()
            df = pd.DataFrame([
                {
                    "Contract": s["details"]["ticker"],
                    "Type": s["details"]["contract_type"],
                    "Strike": s["details"]["strike_price"],
                    "Expiration": s["details"]["expiration_date"],
                    "DTE": (pd.to_datetime(s["details"]["expiration_date"]) - today).days,
                    "Delta": abs(s.get("greeks", {}).get("delta", 0) * 100),
                    "Gamma": s.get("greeks", {}).get("gamma"),
                    "Theta": s.get("greeks", {}).get("theta"),
                    "Vega": s.get("greeks", {}).get("vega"),
                    "IV": s.get("implied_volatility"),
                    "Last Price": s["day"].get("close"),
                }
                for s in snaps
            ])

            # Apply delta filter
            df = df[(df["Delta"] >= min_delta) & (df["Delta"] <= max_delta)]

            # ---------------- SUMMARY ----------------
            st.subheader("📌 Quick Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Total Contracts", len(snaps))
            with col2: st.metric("Filtered", len(df))
            with col3: st.metric("Min Delta", f"{df['Delta'].min():.1f}" if not df.empty else "N/A")
            with col4: st.metric("Max Delta", f"{df['Delta'].max():.1f}" if not df.empty else "N/A")

            # ---------------- CALL/PUT ALIGNMENT ----------------
            calls = df[df["Type"] == "call"].set_index("Strike")
            puts = df[df["Type"] == "put"].set_index("Strike")
            merged = pd.concat([calls, puts], axis=1, keys=["Call", "Put"])

            st.subheader(f"📋 Options Chain for {ticker} - {expiry_filter}")
            st.dataframe(merged, use_container_width=True)

            # ---------------- CSV ----------------
            csv = merged.to_csv().encode("utf-8")
            st.download_button("Download CSV", csv, f"{ticker}_options_chain.csv", "text/csv")
        else:
            st.error("No options data returned.")
