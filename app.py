import streamlit as st
import requests
import datetime
import pandas as pd

# ==============================
# Polygon API Setup
# ==============================
API_KEY = "GuHtoE7JtmzxOpLU_yL_RQOnF1Leliqw"
BASE_URL = "https://api.polygon.io"


def get_spot_price(symbol):
    """Get latest stock price for the underlying symbol"""
    url = f"{BASE_URL}/v2/last/trade/{symbol}"
    params = {"apiKey": API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()["results"]["p"]


def get_option_contracts(symbol):
    """Get all option contracts for a symbol"""
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol,
        "limit": 1000,
        "apiKey": API_KEY
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json().get("results", [])


def get_option_snapshot(option_symbol):
    """Get option snapshot (with greeks & IV)"""
    url = f"{BASE_URL}/v3/snapshot/options/{option_symbol}"
    params = {"apiKey": API_KEY}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return {}
    return r.json().get("results", {})


def build_options_df(contracts, dte_start, dte_end, delta_min, delta_max):
    """Filter contracts by DTE and Delta"""
    today = datetime.date.today()
    rows = []

    for c in contracts:
        try:
            exp_date = datetime.datetime.strptime(c["expiration_date"], "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if not (dte_start <= dte <= dte_end):
                continue

            snapshot = get_option_snapshot(c["ticker"])
            greeks = snapshot.get("greeks", {}) if snapshot else {}
            delta = greeks.get("delta")
            if delta is None:
                continue

            if not (delta_min <= delta <= delta_max):
                continue

            rows.append({
                "Type": c["option_type"].upper(),
                "OptionSymbol": c["ticker"],
                "Strike": c["strike_price"],
                "ExpDate": exp_date,
                "DTE": dte,
                "Delta": delta,
                "Gamma": greeks.get("gamma"),
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "Rho": greeks.get("rho"),
                "IV": greeks.get("implied_volatility"),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


# ==============================
# Streamlit UI
# ==============================
st.title("📊 Polygon Options Filter – By DTE & Delta")

symbol = st.text_input("Symbol", value="SPX")
dte_start = st.number_input("Min DTE (days)", min_value=0, value=5)
dte_end = st.number_input("Max DTE (days)", min_value=1, value=30)
delta_min = st.number_input("Min Delta", min_value=-1.0, max_value=1.0, value=-0.35, step=0.01)
delta_max = st.number_input("Max Delta", min_value=-1.0, max_value=1.0, value=-0.25, step=0.01)

if st.button("Fetch Options"):
    try:
        spot_price = get_spot_price(symbol)
        st.write(f"🔹 Current {symbol} spot price: **${spot_price:.2f}**")

        contracts = get_option_contracts(symbol)
        df = build_options_df(contracts, dte_start, dte_end, delta_min, delta_max)

        if df.empty:
            st.warning("No options found in the given filters.")
        else:
            st.subheader("📌 Filtered Options")
            st.dataframe(df.sort_values(["ExpDate", "Strike", "Type"]).reset_index(drop=True))

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, f"{symbol}_options_filtered.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
