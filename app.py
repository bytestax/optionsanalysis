import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Polygon API Key (add your key here)
POLYGON_API_KEY = "YOUR_API_KEY"

BASE_URL = "https://api.polygon.io"

# Get underlying price (previous close)
def get_underlying_price(symbol):
    url = f"{BASE_URL}/v2/aggs/ticker/{symbol}/prev?apiKey={POLYGON_API_KEY}"
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Error fetching underlying price: {resp.text}")
        return None
    data = resp.json()
    if "results" not in data or len(data["results"]) == 0:
        return None
    return data["results"][0]["c"]  # close price

# Get all options snapshots (with greeks, IV, etc.)
def get_options_snapshot(symbol):
    url = f"{BASE_URL}/v3/snapshot/options/{symbol}?apiKey={POLYGON_API_KEY}"
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Error fetching options snapshot: {resp.text}")
        return []
    return resp.json().get("results", [])

# Filter options by DTE and delta
def filter_options(options, dte_start, dte_end, delta_min, delta_max):
    filtered = []
    today = datetime.today().date()

    for opt in options:
        try:
            details = opt.get("details", {})
            greeks = opt.get("greeks", {})
            iv = opt.get("implied_volatility", None)

            expiration = datetime.strptime(details.get("expiration_date"), "%Y-%m-%d").date()
            dte = (expiration - today).days
            delta = greeks.get("delta", None)

            if delta is None:
                continue

            if dte_start <= dte <= dte_end and delta_min <= abs(delta) <= delta_max:
                filtered.append({
                    "contract_name": details.get("ticker"),
                    "type": details.get("contract_type"),
                    "expiration": expiration,
                    "strike": details.get("strike_price"),
                    "dte": dte,
                    "delta": delta,
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "rho": greeks.get("rho"),
                    "iv": iv,
                    "last_price": opt.get("last_quote", {}).get("bid", None)
                })
        except Exception:
            continue
    return filtered

# ---------------- Streamlit UI ----------------
st.title("📈 Options Chain with Greeks (Polygon.io)")

# Inputs
symbol = st.text_input("Symbol", value="SPX")
dte_start = st.number_input("Min DTE", value=30, step=1)
dte_end = st.number_input("Max DTE", value=60, step=1)
delta_min = st.number_input("Min Delta (abs)", value=0.25, step=0.01)
delta_max = st.number_input("Max Delta (abs)", value=0.35, step=0.01)

if st.button("Get Options Chain"):
    st.write(f"Fetching data for **{symbol}**...")

    underlying = get_underlying_price(symbol)
    if underlying:
        st.write(f"Underlying price (prev close): **{underlying}**")

    options = get_options_snapshot(symbol)
    if not options:
        st.warning("No options data found.")
    else:
        filtered = filter_options(options, dte_start, dte_end, delta_min, delta_max)
        if filtered:
            df = pd.DataFrame(filtered)
            st.dataframe(df)
        else:
            st.warning("No options matched your filters.")
