import streamlit as st
import pandas as pd
import requests

# Polygon API Key
POLYGON_API_KEY = "D2ss7P80Pm42ShCqcexGaZUD59IaKR9M"

# -----------------------------
# Function to fetch option data
# -----------------------------
def fetch_options(symbol: str, min_dte: int, max_dte: int, min_delta: float, max_delta: float):
    """
    Fetch options contracts from Polygon API and filter by DTE and delta.
    """
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={POLYGON_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Polygon API error {response.status_code}: {response.text}")

    data = response.json()
    contracts = []

    # Handle API response format
    if "results" in data and isinstance(data["results"], dict):
        contracts = data["results"].get("options", [])
    elif "results" in data and isinstance(data["results"], list):
        contracts = data["results"]
    else:
        raise Exception("Unexpected response format from Polygon API")

    filtered = []
    for c in contracts:
        details = c.get("details", {})
        greeks = c.get("greeks", {})
        quote = c.get("last_quote", {})

        # DTE calculation
        exp_date = details.get("expiration_date")
        dte = None
        if exp_date:
            try:
                dte = (pd.to_datetime(exp_date) - pd.Timestamp.today()).days
            except Exception:
                dte = None

        row = {
            "symbol": details.get("symbol"),
            "type": details.get("contract_type"),
            "strike": details.get("strike_price"),
            "expiration": exp_date,
            "dte": dte,
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "iv": greeks.get("iv"),
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
            "last_price": quote.get("last"),
        }

        # Apply filters
        if row["dte"] is not None and (min_dte <= row["dte"] <= max_dte):
            if row["delta"] is not None and (min_delta <= row["delta"] <= max_delta):
                filtered.append(row)

    return pd.DataFrame(filtered)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📊 Options Analyzer")

symbol = st.text_input("Enter Symbol (default: SPY)", "SPY")
min_dte = st.number_input("Min DTE", min_value=0, value=10)
max_dte = st.number_input("Max DTE", min_value=0, value=60)
min_delta = st.number_input("Min Delta", min_value=-1.0, max_value=1.0, value=-0.30)
max_delta = st.number_input("Max Delta", min_value=-1.0, max_value=1.0, value=0.70)

if st.button("Fetch Options"):
    with st.spinner("Fetching option contracts..."):
        try:
            df = fetch_options(symbol, min_dte, max_dte, min_delta, max_delta)

            if df.empty:
                st.warning("No options contracts found with the given filters.")
            else:
                st.success(f"Fetched {len(df)} contracts")
                st.dataframe(df)

                # Extra: Show summary stats
                st.subheader("📈 Summary Stats")
                st.write(df.describe(include="all"))

        except Exception as e:
            st.error(f"Error fetching data: {e}")
