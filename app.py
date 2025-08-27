import streamlit as st
import requests
import pandas as pd
import datetime

# ---- CONFIG ----
API_KEY = st.secrets.get("POLYGON_API_KEY", "YOUR_API_KEY_HERE")  # use Streamlit secrets if deployed

# ---- HELPERS ----
def fetch_options_contracts(symbol, min_dte, max_dte):
    url = "https://api.polygon.io/v3/reference/options/contracts"
    today = datetime.date.today()
    start_date = today + datetime.timedelta(days=min_dte)
    end_date = today + datetime.timedelta(days=max_dte)

    params = {
        "underlying_ticker": symbol,
        "expiration_date.gte": start_date.strftime("%Y-%m-%d"),
        "expiration_date.lte": end_date.strftime("%Y-%m-%d"),
        "limit": 1000,
        "order": "asc",
        "sort": "ticker",
        "apiKey": API_KEY,   # ✅ FIX: always append apiKey
    }

    all_contracts = []
    while True:
        resp = requests.get(url, params=params)
        if resp.status_code == 401:
            st.error("🚨 Unauthorized: Check your Polygon API key or subscription plan.")
            return []
        resp.raise_for_status()
        data = resp.json()

        contracts = data.get("results", [])
        if not contracts:
            break

        for c in contracts:
            all_contracts.append({
                "ticker": c.get("ticker"),
                "expiration": c.get("expiration_date"),
                "strike": c.get("strike_price"),
                "contract_type": c.get("contract_type"),
            })

        # Pagination
        next_url = data.get("next_url")
        if not next_url:
            break
        url = next_url + f"&apiKey={API_KEY}"  # ✅ ensure apiKey for next page
        params = {}

    return all_contracts


def fetch_greeks_for_contract(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts/{ticker}"
    params = {"apiKey": API_KEY}
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return {}
    data = resp.json().get("results", {})
    greeks = data.get("greeks", {})
    iv = data.get("implied_volatility")
    return {
        "delta": greeks.get("delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "rho": greeks.get("rho"),
        "iv": iv,
    }


# ---- STREAMLIT APP ----
st.title("📊 Options Chain Explorer (Polygon API)")

symbol = st.text_input("Symbol", "SPY")
min_dte = st.number_input("Min DTE", 1, 365, 30)
max_dte = st.number_input("Max DTE", 1, 365, 60)
min_delta = st.number_input("Min Delta", -1.0, 1.0, -0.30, step=0.01)
max_delta = st.number_input("Max Delta", -1.0, 1.0, 0.30, step=0.01)
use_abs_delta = st.checkbox("Use Absolute Delta (ignore sign)?", True)

if st.button("Get Options Chain"):
    with st.spinner(f"Fetching contracts for {symbol} expiring between {min_dte} and {max_dte} days..."):
        contracts = fetch_options_contracts(symbol, min_dte, max_dte)

    if not contracts:
        st.warning("No contracts found.")
    else:
        df = pd.DataFrame(contracts)

        # ---- Fetch Greeks for each contract ----
        st.info("Fetching Greeks + IV for filtered contracts...")
        greek_data = []
        for _, row in df.iterrows():
            g = fetch_greeks_for_contract(row["ticker"])
            greek_data.append(g)

        greek_df = pd.DataFrame(greek_data)
        df = pd.concat([df, greek_df], axis=1)

        # ---- Apply Delta filter ----
        if use_abs_delta:
            df = df[df["delta"].abs().between(abs(min_delta), abs(max_delta))]
        else:
            df = df[df["delta"].between(min_delta, max_delta)]

        if df.empty:
            st.warning("No contracts matched delta filter.")
        else:
            st.success(f"Total contracts after filtering: {len(df)}")
            st.dataframe(df)
