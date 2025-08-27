import streamlit as st
import requests
from requests_oauthlib import OAuth1
import datetime
import pandas as pd

# ==============================
# Setup your E*TRADE credentials
# ==============================
CONSUMER_KEY = "YOUR_CONSUMER_KEY"
CONSUMER_SECRET = "YOUR_CONSUMER_SECRET"
OAUTH_TOKEN = "YOUR_OAUTH_TOKEN"
OAUTH_TOKEN_SECRET = "YOUR_OAUTH_TOKEN_SECRET"

# Sandbox URL (use live API endpoint once ready)
BASE_URL = "https://api.etrade.com/v1/market"

# Auth object
auth = OAuth1(CONSUMER_KEY,
              client_secret=CONSUMER_SECRET,
              resource_owner_key=OAUTH_TOKEN,
              resource_owner_secret=OAUTH_TOKEN_SECRET)


def get_option_chain(symbol: str):
    """Retrieve the option chain for a given symbol from E*TRADE API"""
    url = f"{BASE_URL}/optionchains.json"
    params = {
        "symbol": symbol,
        "chainType": "CALLPUT",
        "includeGreeks": "true"
    }

    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()
    return response.json()


def parse_options(data):
    """Parse option chain into DataFrame"""
    today = datetime.datetime.now().date()
    rows = []

    if "optionPairs" not in data.get("optionChainResponse", {}):
        return pd.DataFrame()

    for opt in data["optionChainResponse"]["optionPairs"]:
        for contract_type in ["call", "put"]:
            option = opt.get(contract_type)
            if not option:
                continue

            exp_date = datetime.datetime.strptime(option["expiryDate"], "%m/%d/%Y").date()
            dte = (exp_date - today).days
            greeks = option.get("greeks", {})

            rows.append({
                "Type": contract_type.upper(),
                "OptionSymbol": option["optionSymbol"],
                "Strike": option["strikePrice"],
                "ExpDate": exp_date,
                "DTE": dte,
                "Delta": float(greeks.get("delta", 0)),
                "Gamma": greeks.get("gamma"),
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "IV": greeks.get("iv")
            })

    return pd.DataFrame(rows)


def filter_options(df, target_dte, target_delta):
    """Filter options closest to target DTE and delta"""
    df["Score"] = (df["DTE"] - target_dte).abs() + (df["Delta"].abs() - target_delta).abs()
    return df.sort_values("Score")


# ==============================
# Streamlit UI
# ==============================
st.title("📈 E*TRADE Options Explorer")

symbol = st.text_input("Enter stock symbol", value="AAPL")
target_dte = st.number_input("Target DTE", min_value=1, max_value=365, value=45)
target_delta = st.number_input("Target Delta", min_value=0.05, max_value=0.95, value=0.30, step=0.05)

if st.button("Fetch Options"):
    try:
        st.write(f"Fetching option chain for **{symbol}** ...")
        data = get_option_chain(symbol)
        df = parse_options(data)

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
