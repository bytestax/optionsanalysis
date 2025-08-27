import os
import asyncio
from datetime import datetime, timedelta, date

import httpx
import pandas as pd
import requests
import streamlit as st

# -----------------------------
# Config / API key
# -----------------------------
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
BASE_URL = "https://api.polygon.io"

st.set_page_config(page_title="Options Chain (Polygon)", page_icon="📊", layout="wide")

st.title("📊 Options Chain Explorer — Fast (Polygon)")

with st.sidebar:
    st.subheader("API")
    if not POLYGON_API_KEY:
        POLYGON_API_KEY = st.text_input("Polygon API Key", type="password")
    else:
        st.success("API key loaded from environment", icon="✅")

# -----------------------------
# Helpers
# -----------------------------
@st.cache_data(show_spinner=False, ttl=60)
def get_prev_close(symbol: str) -> float | None:
    """Use previous close as reference (works on Starter plan)."""
    url = f"{BASE_URL}/v2/aggs/ticker/{symbol}/prev"
    r = requests.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=30)
    if r.status_code != 200:
        return None
    js = r.json()
    res = js.get("results") or []
    if not res:
        return None
    return float(res[0]["c"])


def date_from_dte(d: int) -> str:
    return (date.today() + timedelta(days=int(d))).strftime("%Y-%m-%d")


@st.cache_data(show_spinner=False, ttl=60)
def fetch_contracts_full(symbol: str, start_iso: str, end_iso: str, max_pages: int = 20, page_size: int = 1000):
    """
    Fetch contracts using /v3/reference/options/contracts with pagination.
    We cap pages to avoid unbounded calls.
    """
    params = {
        "underlying_ticker": symbol,
        "expiration_date.gte": start_iso,
        "expiration_date.lte": end_iso,
        "limit": page_size,
        "apiKey": POLYGON_API_KEY,
    }
    url = f"{BASE_URL}/v3/reference/options/contracts"
    out = []
    pages = 0
    while url and pages < max_pages:
        r = requests.get(url, params=params if pages == 0 else None, timeout=60)
        r.raise_for_status()
        js = r.json()
        out.extend(js.get("results", []))
        url = js.get("next_url")  # Polygon style pagination
        pages += 1
    return out


def calc_dte(exp_iso: str) -> int:
    return (datetime.strptime(exp_iso, "%Y-%m-%d").date() - date.today()).days


def pick_candidates_by_strike(contracts, center: float, max_candidates: int):
    """Pick contracts nearest to center strike to minimize greeks calls."""
    # Only options (no combos)
    rows = [c for c in contracts if c.get("contract_type") in ("call", "put")]
    # Some contracts may not have strike_price; guard it
    rows = [c for c in rows if isinstance(c.get("strike_price"), (int, float))]
    rows.sort(key=lambda c: abs(float(c["strike_price"]) - center))
    return rows[:max_candidates]


async def fetch_one_snapshot(client: httpx.AsyncClient, option_ticker: str):
    url = f"{BASE_URL}/v3/snapshot/options/{option_ticker}"
    try:
        r = await client.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=20.0)
        if r.status_code != 200:
            return option_ticker, None
        js = r.json().get("results")
        return option_ticker, js
    except Exception:
        return option_ticker, None


async def fetch_snapshots_batch(option_tickers: list[str], concurrency: int = 12):
    """Concurrent snapshot fetch with bounded concurrency."""
    results = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        async def task(sym):
            async with sem:
                tkr, res = await fetch_one_snapshot(client, sym)
                results[tkr] = res
        await asyncio.gather(*(task(t) for t in option_tickers))
    return results


def filter_by_delta(df: pd.DataFrame, use_abs: bool, dmin: float, dmax: float) -> pd.DataFrame:
    if use_abs:
        m = (df["delta"].abs() >= abs(dmin)) & (df["delta"].abs() <= abs(dmax))
    else:
        m = (df["delta"] >= dmin) & (df["delta"] <= dmax)
    return df[m]


# -----------------------------
# UI Controls
# -----------------------------
col1, col2, col3 = st.columns([1.2, 1, 1])
with col1:
    symbol = st.text_input("Symbol", value="SPX").strip().upper()
with col2:
    dte_min = st.number_input("Min DTE", min_value=0, value=30, step=1)
with col3:
    dte_max = st.number_input("Max DTE", min_value=0, value=60, step=1)

cc1, cc2, cc3 = st.columns([1, 1, 1])
with cc1:
    delta_min = st.number_input("Min Delta", value=-0.30, format="%.2f")
with cc2:
    delta_max = st.number_input("Max Delta", value=0.30, format="%.2f")
with cc3:
    use_abs_delta = st.checkbox("Use Absolute Delta", value=True)

st.markdown("---")
c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
with c1:
    max_candidates = st.number_input("Max contracts to fetch Greeks for", min_value=50, max_value=2000, value=400, step=50)
with c2:
    concurrency = st.number_input("Concurrent requests", min_value=4, max_value=32, value=12, step=1)
with c3:
    custom_center = st.number_input("Custom center strike (0 = use ATM)", min_value=0.0, value=0.0, step=1.0)
with c4:
    show_download = st.checkbox("Enable CSV download", value=True)

go = st.button("Get Options")

# -----------------------------
# Main flow
# -----------------------------
if go:
    if not POLYGON_API_KEY:
        st.error("API key is required.")
        st.stop()

    # 1) Reference price for ATM
    spot = get_prev_close(symbol)
    if spot is None:
        st.warning("Could not fetch reference price; ATM selection will use median strike.")
    else:
        st.info(f"Reference (prev close) for {symbol}: **{spot:.2f}**")

    # 2) Fetch contracts in DTE window (pagination)
    start_iso = date_from_dte(dte_min)
    end_iso = date_from_dte(dte_max)
    st.write(f"Fetching contracts for **{symbol}** expiring between **{start_iso}** and **{end_iso}** ...")
    try:
        contracts = fetch_contracts_full(symbol, start_iso, end_iso)
    except Exception as e:
        st.error(f"Failed to fetch contracts: {e}")
        st.stop()

    st.success(f"Total contracts returned: {len(contracts)}")

    if not contracts:
        st.stop()

    # Build a quick DF for book-keeping
    base_df = pd.DataFrame(contracts)
    base_df["dte"] = base_df["expiration_date"].apply(calc_dte)
    base_df = base_df[base_df["contract_type"].isin(["call", "put"])]

    # 3) Pick candidate contracts nearest center strike to reduce snapshot calls
    center = custom_center if custom_center > 0 else (spot if spot else base_df["strike_price"].median())
    candidates = pick_candidates_by_strike(base_df.to_dict("records"), center=center, max_candidates=max_candidates)
    st.write(f"Fetching Greeks for **{len(candidates)}** nearest-to-center contracts (center strike: **{center:.2f}**).")

    if not candidates:
        st.warning("No candidates found with a valid strike.")
        st.stop()

    tickers = [c["ticker"] for c in candidates if c.get("ticker")]
    # 4) Concurrent snapshots for Greeks
    with st.spinner("Getting Greeks (concurrent)…"):
        snapshots = asyncio.run(fetch_snapshots_batch(tickers, concurrency=int(concurrency)))

    # 5) Merge results
    rows = []
    for c in candidates:
        snap = snapshots.get(c["ticker"])
        greeks = (snap or {}).get("greeks") or {}
        rows.append(
            {
                "symbol": c["ticker"],
                "underlying": symbol,
                "expiration": c.get("expiration_date"),
                "dte": calc_dte(c.get("expiration_date")),
                "type": c.get("contract_type"),
                "strike": c.get("strike_price"),
                "delta": greeks.get("delta"),
                "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"),
                "vega": greeks.get("vega"),
                "rho": greeks.get("rho"),
                "iv": (snap or {}).get("implied_volatility"),
                "underlying_price": (snap or {}).get("underlying_price"),
            }
        )

    df = pd.DataFrame(rows).dropna(subset=["delta"])

    if df.empty:
        st.warning("No Greeks available for the selected candidates. Try a larger candidate count.")
        st.stop()

    # 6) Final delta filtering
    filtered = filter_by_delta(df, use_abs=use_abs_delta, dmin=delta_min, dmax=delta_max)
    if filtered.empty:
        st.warning("No options matched your delta filter. Try widening the range or increasing candidates.")
        st.stop()

    # 7) Display
    filtered = filtered.sort_values(["expiration", "strike", "type"]).reset_index(drop=True)
    st.subheader("Filtered Options")
    st.dataframe(
        filtered[
            ["symbol", "underlying", "expiration", "dte", "type", "strike",
             "delta", "gamma", "theta", "vega", "rho", "iv", "underlying_price"]
        ],
        use_container_width=True
    )

    # 8) Download
    if show_download:
        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_options_filtered.csv", mime="text/csv")

    # Small summary
    st.caption(
        f"Fetched {len(contracts)} contracts across DTE {dte_min}-{dte_max}. "
        f"Pulled Greeks for {len(candidates)} nearest-to-center contracts with concurrency={concurrency}."
    )
