import streamlit as st
import requests
import pandas as pd
import numpy as np
import time

# -------------------------
# Config
# -------------------------
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE_URL = "https://api.polygon.io/v3/snapshot/options/"

st.set_page_config(page_title="Options Analyzer", layout="wide")
st.title("📊 Options Analyzer — Filters on Top")

# -------------------------
# Inputs
# -------------------------
ticker = st.text_input("Enter stock ticker (e.g. AAPL):", "AAPL").upper()
limit = st.slider("Per-page limit", 10, 1000, 200)

# Fetch button
if st.button("Fetch Options Data"):
    if not ticker:
        st.error("Please enter a ticker symbol.")
    else:
        progress = st.progress(0.0)
        all_results = []
        next_url = f"{BASE_URL}{ticker}?limit={limit}&apiKey={API_KEY}"
        page = 0

        # Fetch loop
        while next_url:
            page += 1
            try:
                resp = requests.get(next_url, timeout=15)
                if resp.status_code != 200:
                    st.error(f"API error {resp.status_code}: {resp.text}")
                    all_results = []
                    break
                data = resp.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
                all_results = []
                break

            results = data.get("results", [])
            if results:
                all_results.extend(results)

            next_url = data.get("next_url")
            if next_url and "apiKey=" not in next_url:
                next_url = next_url + f"&apiKey={API_KEY}"

            progress.progress(min(page / 10.0, 1.0))
            time.sleep(0.2)

        progress.progress(1.0)
        st.write(f"✅ Retrieved {len(all_results)} contracts (raw).")

        if not all_results:
            st.warning("No option contracts returned. Check ticker or API key / quota.")
        else:
            rows = []
            for opt in all_results:
                details = opt.get("details", {}) or {}
                greeks = opt.get("greeks") or {}
                day = opt.get("day") or {}
                underlying = opt.get("underlying_asset") or {}

                rows.append({
                    "Contract": details.get("ticker"),
                    "Type": (details.get("contract_type") or "").lower(),
                    "Strike": details.get("strike_price"),
                    "Expiry": details.get("expiration_date"),
                    "Delta": greeks.get("delta"),
                    "Gamma": greeks.get("gamma"),
                    "Theta": greeks.get("theta"),
                    "Vega": greeks.get("vega"),
                    "IV": opt.get("implied_volatility"),
                    "OI": opt.get("open_interest"),
                    "Last Price": day.get("close"),
                    "Underlying": underlying.get("ticker")
                })

            df = pd.DataFrame(rows)

            # Convert numerics
            for col in ["Strike", "Delta", "Gamma", "Theta", "Vega", "IV", "OI", "Last Price"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            full_df = df.copy()

            # -------------------------
            # FILTERS ON TOP
            # -------------------------
            st.subheader("🔎 Filters")

            col1, col2, col3 = st.columns(3)
            with col1:
                expiry_options = sorted(full_df["Expiry"].dropna().unique().tolist())
                expiry_filter = st.multiselect("Expiry", expiry_options, default=expiry_options)

            with col2:
                type_options = sorted(full_df["Type"].dropna().unique().tolist())
                if not type_options:
                    type_options = ["call", "put"]
                type_filter = st.multiselect("Type", type_options, default=type_options)

            with col3:
                strike_min = float(full_df["Strike"].min()) if not full_df["Strike"].dropna().empty else 0
                strike_max = float(full_df["Strike"].max()) if not full_df["Strike"].dropna().empty else 0
                strike_range = st.slider("Strike Range", strike_min, strike_max, (strike_min, strike_max))

            col4, col5, col6 = st.columns(3)
            with col4:
                delta_min = float(full_df["Delta"].min()) if not full_df["Delta"].dropna().empty else -1
                delta_max = float(full_df["Delta"].max()) if not full_df["Delta"].dropna().empty else 1
                delta_range = st.slider("Delta Range", -1.0, 1.0, (delta_min, delta_max))

            with col5:
                theta_min = float(full_df["Theta"].min()) if not full_df["Theta"].dropna().empty else -1
                theta_max = float(full_df["Theta"].max()) if not full_df["Theta"].dropna().empty else 1
                theta_range = st.slider("Theta Range", theta_min, theta_max, (theta_min, theta_max))

            with col6:
                iv_min = float(full_df["IV"].min()) if not full_df["IV"].dropna().empty else 0
                iv_max = float(full_df["IV"].max()) if not full_df["IV"].dropna().empty else 1
                iv_range = st.slider("IV Range", iv_min, iv_max, (iv_min, iv_max))

            # Quick search
            search_query = st.text_input("Search (contract symbol or strike)", "")

            # -------------------------
            # APPLY FILTERS
            # -------------------------
            filtered = full_df.copy()

            if expiry_filter:
                filtered = filtered[filtered["Expiry"].isin(expiry_filter)]
            if type_filter:
                filtered = filtered[filtered["Type"].isin(type_filter)]
            if not filtered["Strike"].dropna().empty:
                filtered = filtered[(filtered["Strike"] >= strike_range[0]) & (filtered["Strike"] <= strike_range[1])]
            if "Delta" in filtered.columns:
                filtered = filtered[(filtered["Delta"] >= delta_range[0]) & (filtered["Delta"] <= delta_range[1])]
            if "Theta" in filtered.columns:
                filtered = filtered[(filtered["Theta"] >= theta_range[0]) & (filtered["Theta"] <= theta_range[1])]
            if "IV" in filtered.columns:
                filtered = filtered[(filtered["IV"] >= iv_range[0]) & (filtered["IV"] <= iv_range[1])]

            if search_query:
                q = str(search_query).lower()
                filtered = filtered[
                    filtered["Contract"].fillna("").str.lower().str.contains(q) |
                    filtered["Strike"].fillna("").astype(str).str.contains(q)
                ]

            # -------------------------
            # RESULTS
            # -------------------------
            st.write(f"📌 Showing {len(filtered)} contracts (after filters). Full dataset size: {len(full_df)}")
            st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

            # CSV Download
            csv = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"options_{ticker}.csv",
                mime="text/csv"
            )
