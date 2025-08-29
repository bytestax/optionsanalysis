# app.py
import os
import asyncio
from datetime import date, datetime, timedelta
from typing import List

import httpx
import pandas as pd
import requests
import streamlit as st

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Options Chain Explorer (Polygon)", layout="wide")

# Get API key either from environment, streamlit secrets, or user input
DEFAULT_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_API_KEY = st.sidebar.text_input("Polygon API Key", type="password", value=DEFAULT_KEY)

BASE = "https://api.polygon.io"


# -------------------------
# Helpers
# -------------------------
def iso_from_dte(dte: int) -> str:
    return (date.today() + timedelta(days=int(dte))).strftime("%Y-%m-%d")


def calc_dte(exp_iso: str) -> int:
    return (datetime.strptime(exp_iso, "%Y-%m-%d").date() - date.today()).days


def fetch_contracts(symbol: str, start_iso: str, end_iso: str, page_limit: int = 20, page_size: int = 1000) -> List[dict]:
    """Fetch option contracts for given symbol and expiration window"""
    url = f"{BASE}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol,
        "expiration_date.gte": start_iso,
        "expiration_date.lte": end_iso,
        "limit": page_size,
        "apiKey": POLYGON_API_KEY,
    }

    results = []
    pages = 0
    while url and pages < page_limit:
        r = requests.get(url, params=params if pages == 0 else None, timeout=60)
        if r.status_code == 401:
            raise PermissionError("Unauthorized (401). Check your API key and subscription.")
        r.raise_for_status()
        js = r.json()
        items = js.get("results", []) or []
        results.extend(items)
        next_url = js.get("next_url")
        if not next_url:
            break
        url = next_url if "apikey=" in next_url.lower() else f"{next_url}&apiKey={POLYGON_API_KEY}"
        pages += 1

    return results


async def _fetch_snapshot(client: httpx.AsyncClient, ticker: str, sem: asyncio.Semaphore):
    url = f"{BASE}/v3/snapshot/options/{ticker}"
    async with sem:
        try:
            r = await client.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=20.0)
            if r.status_code != 200:
                return ticker, None
            js = r.json().get("results") or {}
            return ticker, js
        except Exception:
            return ticker, None


async def fetch_snapshots_concurrent(tickers: List[str], concurrency: int = 12) -> dict:
    """Fetch snapshots concurrently for many tickers"""
    results = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_snapshot(client, t, sem) for t in tickers]
        for coro in asyncio.as_completed(tasks):
            ticker, snap = await coro
            results[ticker] = snap
    return results


# -------------------------
# UI inputs
# -------------------------
st.title("📊 Options Chain Explorer (Polygon)")

# Symbol selector
symbols = ["SPX", "XSP", "TQQQ", "QQQ", "PLTR", "SOXL", "AAPL", "TSLA"]
symbol = st.selectbox("Symbol", symbols, index=0)
custom_symbol = st.text_input("Or type another symbol").strip().upper()
if custom_symbol:
    symbol = custom_symbol

# Delta range
col1, col2 = st.columns(2)
with col1:
    min_delta = st.number_input("Min Delta (absolute)", min_value=1, max_value=100, value=5, step=1)
with col2:
    max_delta = st.number_input("Max Delta (absolute)", min_value=1, max_value=100, value=35, step=1)

st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    max_snapshot = st.number_input("Max contracts to fetch Greeks for", min_value=50, max_value=2000, value=400, step=50)
with c2:
    concurrency = st.number_input("Concurrent snapshot requests", min_value=4, max_value=48, value=12, step=1)
with c3:
    enable_download = st.checkbox("Enable CSV download", value=True)


# -------------------------
# Main button
# -------------------------
if st.button("Get Options Chain"):
    if not POLYGON_API_KEY:
        st.error("Polygon API Key required (sidebar).")
        st.stop()

    # Handle index options prefix for Polygon
    query_symbol = f"I:{symbol}" if symbol in ["SPX", "XSP"] else symbol

    # First fetch contracts within ~180 days to discover expirations
    try:
        contracts = fetch_contracts(query_symbol, iso_from_dte(0), iso_from_dte(180))
    except Exception as e:
        st.error(f"Failed to fetch contracts: {e}")
        st.stop()

    if not contracts:
        st.warning("No option contracts returned for that symbol.")
        st.stop()

    df_contracts = pd.DataFrame(contracts)
    df_contracts = df_contracts[df_contracts["contract_type"].isin(["call", "put"])]
    df_contracts["dte"] = df_contracts["expiration_date"].apply(calc_dte)

    expiries = sorted(df_contracts["expiration_date"].unique(), key=lambda x: calc_dte(x))
    expiry_labels = [f"{e} ({calc_dte(e)} DTE)" for e in expiries]
    closest_index = min(range(len(expiries)), key=lambda i: abs(calc_dte(expiries[i]) - 45))

    exp_choice = st.selectbox("Choose Expiration", expiry_labels, index=closest_index)
    selected_expiry = expiries[expiry_labels.index(exp_choice)]

    # Filter contracts for chosen expiry
    df_contracts = df_contracts[df_contracts["expiration_date"] == selected_expiry].copy()

    if df_contracts.empty:
        st.warning("No contracts found for selected expiration.")
        st.stop()

    # Get underlying price (prev close)
    prev_close = None
    try:
        r = requests.get(f"{BASE}/v2/aggs/ticker/{query_symbol}/prev", params={"apiKey": POLYGON_API_KEY}, timeout=20)
        if r.status_code == 200:
            res = r.json().get("results") or []
            if res:
                prev_close = float(res[0]["c"])
    except Exception:
        pass

    center = prev_close if prev_close is not None else float(df_contracts["strike_price"].median())
    st.write(f"Using center strike ≈ {center:.2f}")

    # Pick nearest contracts
    df_contracts["abs_dist"] = (df_contracts["strike_price"].astype(float) - center).abs()
    df_candidates = df_contracts.sort_values("abs_dist").head(int(max_snapshot)).copy()

    tickers = df_candidates["ticker"].tolist()
    with st.spinner("Fetching Greeks & IV ..."):
        try:
            snapshots = asyncio.run(fetch_snapshots_concurrent(tickers, concurrency=int(concurrency)))
        except Exception as e:
            st.error(f"Snapshot fetching failed: {e}")
            st.stop()

    rows = []
    for _, row in df_candidates.iterrows():
        t = row["ticker"]
        snap = snapshots.get(t)
        greeks = (snap or {}).get("greeks", {}) if snap else {}
        iv = (snap or {}).get("implied_volatility") if snap else None
        underlying_price = (snap or {}).get("underlying_price") if snap else prev_close

        rows.append({
            "ticker": t,
            "type": row["contract_type"],
            "expiration": row["expiration_date"],
            "dte": int(row["dte"]),
            "strike": float(row["strike_price"]),
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "iv": iv,
            "underlying_price": underlying_price
        })

    df_final = pd.DataFrame(rows).dropna(subset=["delta"])

    if df_final.empty:
        st.warning("No greeks returned. Try increasing max contracts.")
        st.stop()

    # Apply delta filter (absolute, scaled to %)
    df_final["abs_delta"] = (df_final["delta"].abs() * 100).round(1)
    df_filtered = df_final[(df_final["abs_delta"] >= min_delta) & (df_final["abs_delta"] <= max_delta)]

    if df_filtered.empty:
        st.warning("No options matched your delta filter.")
        st.stop()

    # Split into calls and puts
    calls = df_filtered[df_filtered["type"] == "call"].set_index("strike")
    puts = df_filtered[df_filtered["type"] == "put"].set_index("strike")

    merged = calls[["delta","iv","gamma","theta","ticker"]].merge(
        puts[["delta","iv","gamma","theta","ticker"]],
        left_index=True, right_index=True, how="outer", suffixes=("_call","_put")
    ).reset_index().sort_values("strike")

    st.subheader(f"Options Chain for {symbol} (Expiration {selected_expiry}, {calc_dte(selected_expiry)} DTE)")
    st.dataframe(merged, use_container_width=True)

    if enable_download:
        csv = merged.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_{selected_expiry}_options.csv", mime="text/csv")

    st.success(f"Done — displayed {len(merged)} strikes.")
