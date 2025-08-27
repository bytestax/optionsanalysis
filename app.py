import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Polygon API key (replace with your key)
API_KEY = "GuHtoE7JtmzxOpLU_yL_RQOnF1Leliqw"

# Function to fetch option chain from Polygon
def fetch_options_chain(symbol):
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        st.error(f"Error fetching data: {response.status_code} - {response.text}")
        return []
    data = response.json()
    return data.get("results", [])  # <- FIXED

# Function to filter options
def filter_options(options, dte_start, dte_end, delta_min, delta_max, use_abs_delta):
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

            # Use absolute delta if toggle enabled
            delta_check = abs(delta) if use_abs_delta else delta

            if dte_start <= dte <= dte_end and delta_min <= delta_check <= delta_max:
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


# ---------------- Streamlit App ----------------
st.title("Options Chain Explorer (Polygon.io)")

# Inputs
symbol = st.text_input("Symbol", value="SPX")
dte_start = st.number_input("Min DTE", min_value=0, value=30)
dte_end = st.number_input("Max DTE", min_value=0, value=60)
delta_min = st.number_input("Min Delta", value=-0.30, format="%.2f")
delta_max = st.number_input("Max Delta", value=0.30, format="%.2f")

use_abs_delta = st.checkbox("Use Absolute Delta (ignore sign)?", value=False)

if st.button("Get Options Chain"):
    options = fetch_options_chain(symbol)

    if not options:
        st.warning("No option data returned.")
    else:
        # Debug info
        st.write(f"✅ Total contracts pulled: {len(options)}")
        expirations = sorted({opt.get('details', {}).get('expiration_date') for opt in options if opt.get("details")})
        st.write("Available Expirations (sample):", expirations[:10])

        # Apply filter
        filtered = filter_options(options, dte_start, dte_end, delta_min, delta_max, use_abs_delta)

        if not filtered:
            st.warning("⚠️ No options matched your filters. Try adjusting ranges.")
        else:
            df = pd.DataFrame(filtered)
            st.dataframe(df)

            # CSV export
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{symbol}_options.csv",
                mime="text/csv"
            )
