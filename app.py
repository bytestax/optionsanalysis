import time
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Options Strategy Analyzer", layout="wide")
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE = "https://api.polygon.io/v3"

st.title("📊 Options Strategy Analyzer")

# ---------------- SYMBOL INPUT ----------------
default_symbols = ["SPX", "XSP", "TQQQ", "QQQ", "PLTR", "SOXL", "AAPL", "TSLA"]
col0a, col0b = st.columns([2, 2])
with col0a:
    ticker = st.selectbox("Select Symbol", default_symbols, index=0)
with col0b:
    custom_symbol = st.text_input("Or type a custom symbol", "")
if custom_symbol.strip():
    ticker = custom_symbol.strip().upper()

# ---------------- HELPERS ----------------
@st.cache_data(show_spinner=False, ttl=600)
def fetch_all_expirations(symbol: str) -> list[str]:
    """Fetch all expirations for the underlying (paginated)."""
    url = f"{BASE}/reference/options/contracts?underlying_ticker={symbol}&limit=1000&apiKey={API_KEY}"
    expiries = set()
    while url:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Expirations error {r.status_code}: {r.text}")
        data = r.json()
        for res in data.get("results", []):
            if "expiration_date" in res:
                expiries.add(res["expiration_date"])
        url = data.get("next_url")
        if url:
            url += f"&apiKey={API_KEY}"
    return sorted(expiries)

@st.cache_data(show_spinner=False, ttl=600)
def fetch_contracts_for_expiry(symbol: str, expiry: str) -> list[str]:
    """List ALL option contract tickers for a given expiry (paginated)."""
    url = (f"{BASE}/reference/options/contracts"
           f"?underlying_ticker={symbol}&expiration_date={expiry}&limit=1000&apiKey={API_KEY}")
    tickers = []
    while url:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Contracts error {r.status_code}: {r.text}")
        data = r.json()
        tickers.extend([c["ticker"] for c in data.get("results", []) if "ticker" in c])
        url = data.get("next_url")
        if url:
            url += f"&apiKey={API_KEY}"
    return tickers

def fetch_snapshots_for_contracts(contracts: list[str]) -> list[dict]:
    """
    Fetch each contract snapshot individually (reliable, includes greeks, IV, OI, prices).
    Shows a progress bar. Handles occasional errors gracefully.
    """
    results = []
    if not contracts:
        return results
    prog = st.progress(0.0, text="Fetching option snapshots...")
    errors = 0
    for i, c in enumerate(contracts, start=1):
        url = f"{BASE}/snapshot/options/{c}?apiKey={API_KEY}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                snap = r.json().get("results")
                if snap:
                    results.append(snap)
            else:
                errors += 1
        except Exception:
            errors += 1
        # simple pacing to be gentle on rate limits
        time.sleep(0.05)
        prog.progress(i/len(contracts), text=f"Fetched {i}/{len(contracts)} (errors: {errors})")
    prog.empty()
    return results

def build_df_from_snaps(snaps: list[dict]) -> pd.DataFrame:
    today = pd.Timestamp.today().normalize()
    rows = []
    for s in snaps:
        details = s.get("details", {}) or {}
        greeks = s.get("greeks", {}) or {}
        day = s.get("day", {}) or {}
        # Robust delta handling -> absolute, as percent (0..100), NaN if missing
        raw_delta = greeks.get("delta", None)
        delta_pct = abs(float(raw_delta)) * 100 if raw_delta is not None else pd.NA
        rows.append({
            "Contract": details.get("ticker"),
            "Type": details.get("contract_type"),
            "Strike": details.get("strike_price"),
            "Expiration": details.get("expiration_date"),
            "DTE": (pd.to_datetime(details.get("expiration_date")) - today).days
                   if details.get("expiration_date") else pd.NA,
            "Delta": delta_pct,
            "Gamma": greeks.get("gamma"),
            "Theta": greeks.get("theta"),
            "Vega": greeks.get("vega"),
            "IV": s.get("implied_volatility"),
            "Last Price": day.get("close"),
            "Volume": day.get("volume"),
            "OI": s.get("open_interest"),
        })
    df = pd.DataFrame(rows)
    # Ensure numeric types for filtering
    for col in ["Strike", "Delta", "Gamma", "Theta", "Vega", "IV", "Last Price", "Volume", "OI"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def filter_by_delta_abs(df: pd.DataFrame, min_delta: float, max_delta: float) -> pd.DataFrame:
    """Filter using absolute delta in percent. Handles NaNs safely."""
    work = df.copy()
    work = work[work["Delta"].notna()]
    return work[(work["Delta"] >= float(min_delta)) & (work["Delta"] <= float(max_delta))]

# --- Strike helper functions ---
def pick_nearest_by_delta(df: pd.DataFrame, option_type: str, target_delta: float) -> pd.Series | None:
    side = df[(df["Type"] == option_type) & df["Delta"].notna()]
    if side.empty:
        return None
    idx = (side["Delta"] - float(target_delta)).abs().idxmin()
    return side.loc[idx]

def pick_nearest_by_strike(df: pd.DataFrame, option_type: str, target_strike: float) -> pd.Series | None:
    side = df[(df["Type"] == option_type) & df["Strike"].notna()]
    if side.empty:
        return None
    idx = (side["Strike"] - float(target_strike)).abs().idxmin()
    return side.loc[idx]

# ---------------- EXPIRATION (default ~45 DTE) ----------------
expiries = []
expiry_filter = None
try:
    if ticker:
        expiries = fetch_all_expirations(ticker)
        if expiries:
            # find expiry closest to 45 DTE
            dtes = [abs((pd.to_datetime(x) - pd.Timestamp.today()).days - 45) for x in expiries]
            default_idx = int(pd.Series(dtes).idxmin())
            expiry_filter = st.selectbox("Expiration (choose DTE)", expiries, index=default_idx)
        else:
            st.warning("No expirations found for this symbol.")
except Exception as e:
    st.error(str(e))

# ---------------- DELTA RANGE ----------------
c1, c2 = st.columns(2)
with c1:
    min_delta = st.number_input("Min Δ (abs, %)", value=5.0, step=1.0)
with c2:
    max_delta = st.number_input("Max Δ (abs, %)", value=35.0, step=1.0)

# ---------------- FETCH & SHOW ----------------
if st.button("Get Option Chain") and expiry_filter:
    with st.spinner("Building option chain..."):
        try:
            contracts = fetch_contracts_for_expiry(ticker, expiry_filter)
            snaps = fetch_snapshots_for_contracts(contracts)
            raw_df = build_df_from_snaps(snaps)

            total_contracts = len(raw_df)
            # Apply delta filter (ABS in %)
            df = filter_by_delta_abs(raw_df, min_delta, max_delta)
            filtered_count = len(df)

            # ------- Quick Summary -------
            st.subheader("📌 Quick Summary")
            cA, cB, cC, cD = st.columns(4)
            with cA: st.metric("Contracts (expiry)", total_contracts)
            with cB: st.metric("Filtered by Δ", filtered_count)
            # ATM (by call delta ≈ 50) as robust proxy (no spot dependency)
            atm_row = None
            calls_only = df[df["Type"] == "call"]
            if not calls_only.empty:
                atm_row = calls_only.iloc[(calls_only["Delta"] - 50).abs().argsort()[:1]]
                atm_strike = float(atm_row["Strike"].values[0])
                with cC: st.metric("ATM (≈Δ50 Call)", f"{atm_strike:.2f}")
            else:
                with cC: st.metric("ATM (≈Δ50 Call)", "N/A")
            if not df.empty:
                with cD: st.metric("Δ Range (shown)", f"{df['Delta'].min():.1f} → {df['Delta'].max():.1f}")
            else:
                with cD: st.metric("Δ Range (shown)", "N/A")

            # ------- Align Calls vs Puts by Strike -------
            view_cols = ["Contract","DTE","Delta","IV","Gamma","Theta","Last Price","Volume","OI"]
            calls = df[df["Type"] == "call"].set_index("Strike")[view_cols].rename(
                columns={c: f"Call {c}" for c in view_cols}
            )
            puts = df[df["Type"] == "put"].set_index("Strike")[view_cols].rename(
                columns={c: f"Put {c}" for c in view_cols}
            )
            merged = pd.concat([calls, puts], axis=1).sort_index()

            st.subheader(f"📋 Options Chain (Δ abs in %, {ticker}, {expiry_filter})")
            st.dataframe(merged, use_container_width=True)

            # ------- Download -------
            st.download_button(
                "Download CSV",
                merged.to_csv().encode("utf-8"),
                file_name=f"{ticker}_{expiry_filter}_options_chain.csv",
                mime="text/csv"
            )

            # ------- Strike Helpers (Call & Put) -------
            st.subheader("🎯 Strike Helpers")

            tab1, tab2 = st.tabs(["Pick by Target Delta", "Pick by Strike Price"])

            with tab1:
                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    tgt_call_delta = st.number_input("Target Call Δ (abs, %)", value=30.0, step=1.0, key="tgt_call_delta")
                    call_pick = pick_nearest_by_delta(df, "call", tgt_call_delta)
                    if call_pick is not None:
                        st.write("**Nearest Call (by Δ):**")
                        st.dataframe(call_pick.to_frame().T, use_container_width=True)
                    else:
                        st.info("No call found for the current filters.")
                with dcol2:
                    tgt_put_delta = st.number_input("Target Put Δ (abs, %)", value=20.0, step=1.0, key="tgt_put_delta")
                    put_pick = pick_nearest_by_delta(df, "put", tgt_put_delta)
                    if put_pick is not None:
                        st.write("**Nearest Put (by Δ):**")
                        st.dataframe(put_pick.to_frame().T, use_container_width=True)
                    else:
                        st.info("No put found for the current filters.")

            with tab2:
                # Suggest a starting strike ~ ATM if available
                default_strike = float(atm_row["Strike"].values[0]) if atm_row is not None else (df["Strike"].median() if not df.empty else 0.0)
                scol1, scol2 = st.columns(2)
                with scol1:
                    target_call_strike = st.number_input("Target Call Strike", value=float(default_strike or 0.0), step=1.0, key="tgt_call_strike")
                    call_by_strike = pick_nearest_by_strike(df, "call", target_call_strike)
                    if call_by_strike is not None:
                        st.write("**Nearest Call (by Strike):**")
                        st.dataframe(call_by_strike.to_frame().T, use_container_width=True)
                    else:
                        st.info("No call found near that strike.")
                with scol2:
                    target_put_strike = st.number_input("Target Put Strike", value=float(default_strike or 0.0), step=1.0, key="tgt_put_strike")
                    put_by_strike = pick_nearest_by_strike(df, "put", target_put_strike)
                    if put_by_strike is not None:
                        st.write("**Nearest Put (by Strike):**")
                        st.dataframe(put_by_strike.to_frame().T, use_container_width=True)
                    else:
                        st.info("No put found near that strike.")

        except Exception as e:
            st.error(str(e))
