import streamlit as st
import requests
import datetime
import pandas as pd

# ==============================
# Polygon API Setup
# ==============================
API_KEY = "YGuHtoE7JtmzxOpLU_yL_RQOnF1Leliqw"
BASE_URL = "https://api.polygon.io"


def get_spot_price(symbol):
    """Get latest stock price for the underlying symbol"""
    url = f"{BASE_URL}/v2/last/trade/{symbol}"
    params = {"apiKey": API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()["results"]["p"]


def get_option_contracts(symbol, exp_date=None):
    """Get all option contracts for a symbol (optionally filtered by expiration date)"""
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol,
        "limit": 1000,
        "apiKey": API_KEY
    }
    if exp_date:
        params["expiration_date"] = exp_date

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


def build_options_df(contracts, spot_price, target_strike=None):
    """Filter for ~50 strikes around spot or target strike"""
    today = datetime.date.today()
    rows = []

    # pick target strike center
    center_strike = target_strike if target_strike else spot_price

    # filter to 50 strikes (±25 around center)
    strikes = sorted({c["strike_price"] for c in contracts})
    if not strikes:
        return pd.DataFrame()

    # find nearest strike to center
    closest = min(strikes, key=lambda x: abs(x - center_strike))
    idx = strikes.index(closest)

    # slice ±25
    window = strikes[max(0, idx - 25): idx + 25]

    # filter contracts in that window
    subset = [c for c in contracts if c["strike_price"] in window]

    for c in subset:
        try:
            exp_date = datetime.datetime.strptime(c["expiration_date"], "%Y-%m-%d").date()
            dte = (exp_date - today).days
            snapshot = get_option_snapshot(c["ticker"])
            greeks = snapshot.get("greeks", {}) if snapshot else {}

            rows.append({
                "Type": c["option_type"].upper(),
                "OptionSymbol": c["ticker"],
                "Strike": c["strike_price"],
                "ExpDate": exp_date,
                "DTE": dte,
                "Delta": greeks.get("delta"),
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
st.title("📈 Polygon Options Explorer – Strikes Around Spot")

symbol = st.text_input("Enter stock symbol", value="AAPL")
exp_date = st.text_input("Expiration Date (YYYY-MM-DD, optional)", value="")
custom_strike = st.number_input("Custom Strike (leave 0 to use spot price)", min_value=0.0, value=0.0, step=1.0)

if st.button("Fetch Options"):
    try:
        spot_price = get_spot_price(symbol)
        st.write(f"🔹 Current {symbol} spot price: **${spot_price:.2f}**")

        contracts = get_option_contracts(symbol, exp_date if exp_date else None)
        df = build_options_df(contracts, spot_price, target_strike=(custom_strike if custom_strike > 0 else None))

        if df.empty:
            st.warning("No options found.")
        else:
            st.subheader("📌 Calls & Puts – Next 50 Strikes Around Spot/Custom Strike")
            st.dataframe(df.sort_values(["ExpDate", "Strike", "Type"]).reset_index(drop=True))

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, f"{symbol}_options.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")
