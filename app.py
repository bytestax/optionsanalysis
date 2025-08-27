import os
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Get API key from environment or user input
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not POLYGON_API_KEY:
    st.warning("⚠️ No Polygon API key set in environment. Please enter manually below.")
    POLYGON_API_KEY = st.text_input("Enter Polygon API Key", type="password")

BASE_URL = "https://api.polygon.io"


# ---- Helpers ----
def fetch_option_contracts(symbol, start_date, end_date):
    """Fetch option contracts for a symbol between expiration dates."""
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol,
        "expiration_date.gte": start_date,
        "expiration_date.lte": end_date,
        "limit": 1000,
        "apiKey": POLYGON_API_KEY,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json().get("results", [])


def fetch_greeks(option_symbols):
    """Fetch Greeks for a list of option contract symbols using snapshot."""
    results = []
    for sym in option_symbols:
        url = f"{BASE_URL}/v3/snapshot/options/{sym}"
        params = {"apiKey": POLYGON_API_KEY}
        resp = requests.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json().get("results")
            if data and "greeks" in data:
                results.append({
                    "symbol": sym,
                    "delta": data["greeks"].get("delta"),
                    "gamma": data["greeks"].get("gamma"),
                    "theta": data["greeks"].get("theta"),
                    "vega": data["greeks"].get("vega"),
                    "rho": data["greeks"].get("rho"),
                    "iv": data.get("implied_volatility"),
                    "underlying_price": data.get("underlying_price")
                })
    return results


def calculate_dte(expiration_date):
    today = datetime.utcnow().date()
    exp = datetime.strptime(expiration_date, "%Y-%m-%d").date()
    return (exp - today).days


# ---- Streamlit App ----
st.title("📊 Options Chain Explorer (Polygon API)")

# Inputs
symbol = st.text_input("Symbol", "SPY")
min_dte = st.number_input("Min DTE", min_value=0, value=30)
max_dte = st.number_input("Max DTE", min_value=0, value=60)
min_delta = st.number_input("Min Delta", value=-0.30, format="%.2f")
max_delta = st.number_input("Max Delta", value=0.30, format="%.2f")
use_abs_delta = st.checkbox("Use Absolute Delta (ignore sign)?", True)

if st.button("Get Options Chain"):
    if not POLYGON_API_KEY:
        st.error("❌ API Key required!")
    else:
        start_date = (datetime.utcnow().date() + timedelta(days=min_dte)).strftime("%Y-%m-%d")
        end_date = (datetime.utcnow().date() + timedelta(days=max_dte)).strftime("%Y-%m-%d")

        st.write(f"Fetching contracts for {symbol} expiring between {start_date} and {end_date}...")

        contracts = fetch_option_contracts(symbol, start_date, end_date)
        st.success(f"Total contracts pulled: {len(contracts)}")

        if contracts:
            df = pd.DataFrame(contracts)

            # Add DTE
            df["dte"] = df["expiration_date"].apply(calculate_dte)

            # Filter only Calls and Puts
            df = df[df["contract_type"].isin(["call", "put"])]

            # Pull Greeks for each option
            st.write("Fetching Greeks...")
            greek_data = fetch_greeks(df["ticker"].tolist())

            if greek_data:
                gdf = pd.DataFrame(greek_data)
                merged = df.merge(gdf, left_on="ticker", right_on="symbol", how="inner")

                # Apply delta filters
                if use_abs_delta:
                    merged = merged[
                        (merged["delta"].abs() >= abs(min_delta)) &
                        (merged["delta"].abs() <= abs(max_delta))
                    ]
                else:
                    merged = merged[
                        (merged["delta"] >= min_delta) &
                        (merged["delta"] <= max_delta)
                    ]

                if not merged.empty:
                    st.dataframe(
                        merged[
                            [
                                "symbol", "expiration_date", "dte",
                                "contract_type", "strike_price",
                                "delta", "gamma", "theta", "vega", "rho", "iv"
                            ]
                        ]
                    )
                else:
                    st.warning("⚠️ No contracts matched your delta filters.")
            else:
                st.error("❌ Could not fetch Greeks. Check your Polygon subscription tier.")
        else:
            st.warning("⚠️ No contracts found in that DTE range.")
