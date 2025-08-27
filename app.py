import streamlit as st
import requests
from requests_oauthlib import OAuth1Session, OAuth1
import datetime
import pandas as pd

# ==============================
# API endpoints
# Sandbox URLs: use api.etrade.com for production
# ==============================
REQUEST_TOKEN_URL = "https://apisb.etrade.com/oauth/request_token"
AUTHORIZE_URL = "https://apisb.etrade.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://apisb.etrade.com/oauth/access_token"
BASE_URL = "https://apisb.etrade.com/v1/market"


# ==============
# Helper methods
# ==============
def get_option_chain(symbol: str, auth):
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
st.title("📈 E*TRADE Options Explorer with OAuth")

# Step 1: Input API keys
st.sidebar.header("🔑 API Authentication")
consumer_key = st.sidebar.text_input("Consumer Key")
consumer_secret = st.sidebar.text_input("Consumer Secret", type="password")

if consumer_key and consumer_secret:
    # Step 2: Get request token
    if st.sidebar.button("Generate Authorization URL"):
        oauth = OAuth1Session(consumer_key, client_secret=consumer_secret, callback_uri="oob")
        try:
            fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
            st.session_state["resource_owner_key"] = fetch_response.get("oauth_token")
            st.session_state["resource_owner_secret"] = fetch_response.get("oauth_token_secret")

            authorization_url = oauth.authorization_url(AUTHORIZE_URL)
            st.success("Authorization URL generated! Please open this in your browser, login, and authorize the app.")
            st.code(authorization_url)
        except Exception as e:
            st.error(f"Error fetching request token: {e}")

    # Step 3: Enter PIN
    verifier = st.sidebar.text_input("Enter Verifier (PIN)")

    if verifier and "resource_owner_key" in st.session_state:
        if st.sidebar.button("Get Access Token"):
            try:
                oauth = OAuth1Session(
                    consumer_key,
                    client_secret=consumer_secret,
                    resource_owner_key=st.session_state["resource_owner_key"],
                    resource_owner_secret=st.session_state["resource_owner_secret"],
                    verifier=verifier,
                )
                access_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)

                st.session_state["oauth_token"] = access_tokens["oauth_token"]
                st.session_state["oauth_token_secret"] = access_tokens["oauth_token_secret"]

                st.success("✅ Access tokens generated successfully!")
                st.json(access_tokens)

            except Exception as e:
                st.error(f"Error fetching access token: {e}")


# Step 4: Use Access Token to fetch options
if "oauth_token" in st.session_state:
    st.subheader("Options Chain Explorer")

    symbol = st.text_input("Enter stock symbol", value="AAPL")
    target_dte = st.number_input("Target DTE", min_value=1, max_value=365, value=45)
    target_delta = st.number_input("Target Delta", min_value=0.05, max_value=0.95, value=0.30, step=0.05)

    if st.button("Fetch Options"):
        try:
            auth = OAuth1(
                consumer_key,
                client_secret=consumer_secret,
                resource_owner_key=st.session_state["oauth_token"],
                resource_owner_secret=st.session_state["oauth_token_secret"]
            )

            data = get_option_chain(symbol, auth)
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
            st.error(f"Error fetching options: {e}")
