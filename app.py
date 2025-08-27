import streamlit as st
import requests
import datetime
import pandas as pd

# ==============================
# Polygon API Setup
# ==============================
API_KEY = "GuHtoE7JtmzxOpLU_yL_RQOnF1Leliqw"
BASE_URL = "https://api.polygon.io"


def get_option_contracts(symbol):
    """Get all option contracts for a symbol"""
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol,
        "limit": 1000,
        "apiKey": API_KEY
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("results", [])


def get_option_snapshot(option_symbol):
    """Get option snapshot with greeks"""
    url = f"{BASE_URL}/v3/snapshot/options/{option_symbol}"
    params = {"apiKey": API_KEY}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return {}
    data = response.json()
    return data.get("results", {})


def build_options_df(contracts):
    today = datetime.date.today()
    rows = []

    for c in contracts:
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
                "IV": greeks.get("implied_volatility")
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def filter_options(df, target_dte, target_delta):
    df = df.dropna(subset=["Delta"])
    df["Score"] = (df["DTE"] - target_dte).abs() + (df["Delta"].abs() - target_delta).abs()
    return df.sort_values("Score")


# ==============================
# Streamlit UI
# ==============================
st.title("📈 Polygon Options Explorer")

symbol = st.text_input("Enter stock symbol", value="AAPL")
target_dte = st.number_input("Target DTE", min_value=1, max_value=365, value=45)
target_delta = st.number_input("Target Delta", min_value=0.05, max_value=0.95, value=0.30, step=0.05)

if st.button("Fetch Options"):
    try:
        st.write(f"Fetching option chain for **{symbol}** ...")
        contracts = get_option_contracts(symbol)
        df = build_options_df(contracts)

        if df.empty:
            st.warning("No options found.")
        else:
            st.subheader("📌 All Available Expirations (DTE)")
            exp_table = df.groupby("ExpDate")["DTE"].first().reset_index()
            st.table(exp_table)

            st.subheader(f"🎯 Closest matches to DTE≈{target_dte}, Δ≈{target_delta}")
            filtered = filter_options(df, target_dte, target_delta)
            st.dataframe(filtered.head(20))

    except Exception as e:
        st.error(f"Error: {e}")
