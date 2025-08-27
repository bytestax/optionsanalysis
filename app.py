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
    """
    Fetch contracts from /v3/reference/options/contracts with pagination.
    Always ensures apiKey is present (pagination next_url also gets apiKey appended).
    """
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
        # ensure apiKey is on next page
        url = next_url if next_url.lower().find("apikey=") >= 0 else f"{next_url}&apiKey={POLYGON_API_KEY}"
        pages += 1

    return results


async def _fetch_snapshot(client: httpx.AsyncClient, ticker: str, sem: asyncio.Semaphore):
    """
    Fetch snapshot for a single option ticker (returns None on failure).
    """
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
    """
    Fetch snapshots for many tickers concurrently with a bound on concurrency.
    Returns dict: { ticker: snapshot_json_or_None }
    """
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

col1, col2, col3 = st.columns([1.2, 1, 1])
with col1:
    symbol = st.text_input("Symbol", value="SPY").strip().upper()
with col2:
    min_dte = st.number_input("Min DTE", min_value=0, value=30, step=1)
with col3:
    max_dte = st.number_input("Max DTE", min_value=0, value=60, step=1)

col4, col5, col6 = st.columns([1, 1, 1])
with col4:
    min_delta = st.number_input("Min Delta", value=-0.30, format="%.2f")
with col5:
    max_delta = st.number_input("Max Delta", value=0.30, format="%.2f")
with col6:
    use_abs_delta = st.checkbox("Use Absolute Delta (ignore sign)?", value=True)

st.markdown("---")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    max_snapshot = st.number_input("Max contracts to fetch Greeks for", min_value=10, max_value=2000, value=400, step=10)
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

    # compute date window
    start_iso = iso_from_dte(min_dte)
    end_iso = iso_from_dte(max_dte)
    st.info(f"Fetching contracts for {symbol} with expirations between {start_iso} and {end_iso} ...")

    try:
        contracts = fetch_contracts(symbol, start_iso, end_iso)
    except PermissionError as pe:
        st.error(str(pe))
        st.stop()
    except Exception as e:
        st.error(f"Failed to fetch contracts: {e}")
        st.stop()

    st.success(f"Total contracts returned: {len(contracts)}")

    if not contracts:
        st.warning("No option contracts returned for that DTE window.")
        st.stop()

    # Build DataFrame and compute DTE
    df_contracts = pd.DataFrame(contracts)
    # Keep only calls/puts and rows with strike and ticker
    df_contracts = df_contracts[df_contracts["contract_type"].isin(["call", "put"])]
    df_contracts = df_contracts[df_contracts["strike_price"].notnull() & df_contracts["ticker"].notnull()].copy()
    df_contracts["dte"] = df_contracts["expiration_date"].apply(calc_dte)

    # Keep only rows inside DTE window (defensive)
    df_contracts = df_contracts[(df_contracts["dte"] >= min_dte) & (df_contracts["dte"] <= max_dte)]

    if df_contracts.empty:
        st.warning("After computing DTE, no contracts fall in your chosen window.")
        st.stop()

    st.write(f"Contracts after DTE filter: {len(df_contracts)}")

    # Sort by proximity to ATM (we use prev close if available)
    # Attempt to get previous close for ATM; fallback to median strike
    prev_close = None
    try:
        r = requests.get(f"{BASE}/v2/aggs/ticker/{symbol}/prev", params={"apiKey": POLYGON_API_KEY}, timeout=20)
        if r.status_code == 200:
            res = r.json().get("results") or []
            if res:
                prev_close = float(res[0]["c"])
    except Exception:
        prev_close = None

    center = prev_close if prev_close is not None else float(df_contracts["strike_price"].median())
    st.write(f"Using center strike ≈ {center:.2f} to pick nearest contracts to fetch Greeks (prev close used if available).")

    # Pick nearest contracts by strike (both calls and puts) up to max_snapshot
    df_contracts["abs_dist"] = (df_contracts["strike_price"].astype(float) - center).abs()
    df_candidates = df_contracts.sort_values("abs_dist").head(int(max_snapshot)).copy()
    st.write(f"Will fetch Greeks for {len(df_candidates)} contracts (top nearest to center).")

    # Prepare tickers to fetch
    tickers = df_candidates["ticker"].tolist()

    # Concurrently fetch snapshots (greeks, iv)
    with st.spinner("Fetching Greeks & IV for selected contracts (concurrent)..."):
        try:
            snapshots = asyncio.run(fetch_snapshots_concurrent(tickers, concurrency=int(concurrency)))
        except Exception as e:
            st.error(f"Snapshot fetching failed: {e}")
            st.stop()

    # Build merged results
    rows = []
    for _, row in df_candidates.iterrows():
        t = row["ticker"]
        snap = snapshots.get(t)
        greeks = (snap or {}).get("greeks", {}) if snap else {}
        iv = (snap or {}).get("implied_volatility") if snap else None
        # use underlying_price if snapshot provides it, else prev_close
        underlying_price = (snap or {}).get("underlying_price") if snap else None

        rows.append({
            "ticker": t,
            "type": row["contract_type"],
            "expiration": row["expiration_date"],
            "dte": int(row["dte"]),
            "strike": float(row["strike_price"]),
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "rho": greeks.get("rho"),
            "iv": iv,
            "underlying_price": underlying_price if underlying_price is not None else prev_close
        })

    df_final = pd.DataFrame(rows)

    # Drop rows without delta (no greeks available)
    before = len(df_final)
    df_final = df_final.dropna(subset=["delta"])
    after = len(df_final)
    st.write(f"Snapshots returned with greeks: {after}/{before}")

    if df_final.empty:
        st.warning("No greeks returned for the selected candidates. Try increasing 'Max contracts to fetch Greeks for' or check subscription.")
        st.stop()

    # Apply delta filters (signed or absolute)
    if use_abs_delta:
        mask = (df_final["delta"].abs() >= abs(min_delta)) & (df_final["delta"].abs() <= abs(max_delta))
    else:
        mask = (df_final["delta"] >= min_delta) & (df_final["delta"] <= max_delta)

    df_filtered = df_final[mask].sort_values(["expiration", "strike", "type"]).reset_index(drop=True)

    if df_filtered.empty:
        st.warning("No options matched your delta filter. Try widening delta range or increasing max contracts to fetch greeks for.")
        # still show available greeks to help debug
        st.subheader("Greeks returned (unfiltered)")
        st.dataframe(df_final.sort_values(["expiration", "strike", "type"]).reset_index(drop=True))
        st.stop()

    # Display results
    st.subheader("Filtered Options (with Greeks & IV)")
    st.dataframe(df_filtered, use_container_width=True)

    if enable_download:
        csv = df_filtered.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_options_filtered.csv", mime="text/csv")

    st.success(f"Done — displayed {len(df_filtered)} contracts (greeks fetched for {len(tickers)} candidates).")
