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
st.title("📊 Options Analyzer — Stable Filters & Charts")

# -------------------------
# Inputs
# -------------------------
ticker = st.text_input("Enter stock ticker (e.g. AAPL):", "AAPL").upper()
limit = st.slider("Per-page limit (API supports up to 1000, keep modest to avoid rate limits)", 10, 1000, 200)

# Fetch button
if st.button("Fetch Options Data"):
    if not ticker:
        st.error("Please enter a ticker symbol.")
    else:
        progress = st.progress(0.0)
        all_results = []
        next_url = f"{BASE_URL}{ticker}?limit={limit}&apiKey={API_KEY}"
        page = 0

        # -------------------------
        # Fetch loop (safe pagination)
        # -------------------------
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

            # handle next page url returned by API
            next_url = data.get("next_url")
            if next_url:
                # ensure apiKey present exactly once
                if "apiKey=" not in next_url:
                    next_url = next_url + f"&apiKey={API_KEY}"
            # update progress (capped)
            progress.progress(min(page / 10.0, 1.0))
            time.sleep(0.2)  # tiny pause to be friendly to API

        progress.progress(1.0)
        st.write(f"✅ Retrieved {len(all_results)} contracts (raw).")

        if not all_results:
            st.warning("No option contracts returned. Check ticker or API key / quota.")
        else:
            # -------------------------
            # Normalize into DataFrame (safe extraction)
            # -------------------------
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

            # -------------------------
            # Convert numeric fields (coerce errors → NaN)
            # -------------------------
            for col in ["Strike", "Delta", "Gamma", "Theta", "Vega", "IV", "OI", "Last Price"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # keep a full copy for "show all" behavior
            full_df = df.copy()

            # -------------------------
            # Sidebar filters (robust & default to "all")
            # -------------------------
            st.sidebar.header("🔎 Filters (defaults = show everything)")

            # Expiry multi-select (default: all unique sorted)
            expiry_options = sorted(full_df["Expiry"].dropna().unique().tolist())
            expiry_filter = st.sidebar.multiselect("Expiry", expiry_options, default=expiry_options)

            # Contract type multi-select (call/put)
            type_options = sorted(full_df["Type"].dropna().unique().tolist())
            if not type_options:
                type_options = ["call", "put"]
            type_filter = st.sidebar.multiselect("Contract Type", type_options, default=type_options)

            # Strike range slider
            if full_df["Strike"].dropna().empty:
                strike_range = (0.0, 0.0)
            else:
                strike_min = float(full_df["Strike"].min())
                strike_max = float(full_df["Strike"].max())
                strike_range = st.sidebar.slider("Strike Range", strike_min, strike_max, (strike_min, strike_max))

            # Delta range slider (if no deltas exist, default -1..1)
            if full_df["Delta"].dropna().empty:
                delta_default_min, delta_default_max = -1.0, 1.0
            else:
                delta_default_min = float(full_df["Delta"].min())
                delta_default_max = float(full_df["Delta"].max())
                # clamp into [-1,1]
                delta_default_min = max(-1.0, min(1.0, delta_default_min))
                delta_default_max = max(-1.0, min(1.0, delta_default_max))
            delta_range = st.sidebar.slider("Delta Range", -1.0, 1.0, (delta_default_min, delta_default_max))

            # Theta range slider (if available)
            if full_df["Theta"].dropna().empty:
                theta_exists = False
            else:
                theta_exists = True
                theta_min = float(full_df["Theta"].min())
                theta_max = float(full_df["Theta"].max())
                theta_range = st.sidebar.slider("Theta Range", theta_min, theta_max, (theta_min, theta_max))

            # IV range slider
            if full_df["IV"].dropna().empty:
                iv_default_min, iv_default_max = 0.0, float(full_df["IV"].max(skipna=True) or 2.0)
            else:
                iv_default_min = float(full_df["IV"].min())
                iv_default_max = float(full_df["IV"].max())
            iv_range = st.sidebar.slider("IV Range", float(iv_default_min), float(iv_default_max or iv_default_min + 1.0),
                                         (float(iv_default_min), float(iv_default_max or iv_default_min + 1.0)))

            # -------------------------
            # Quick search in main panel
            # -------------------------
            st.subheader("🔍 Quick Search (contract symbol or strike)")
            search_query = st.text_input("", "")

            # -------------------------
            # Apply filters safely
            # -------------------------
            filtered = full_df.copy()

            # expiry & type (these default to "all" selections)
            if expiry_filter:
                filtered = filtered[filtered["Expiry"].isin(expiry_filter)]
            if type_filter:
                filtered = filtered[filtered["Type"].isin(type_filter)]

            # strike numeric bounds
            if "Strike" in filtered.columns and not filtered["Strike"].dropna().empty:
                low_s, high_s = float(strike_range[0]), float(strike_range[1])
                filtered = filtered[(filtered["Strike"] >= low_s) & (filtered["Strike"] <= high_s)]

            # delta numeric bounds (use >= <= to avoid pandas version differences)
            if "Delta" in filtered.columns:
                dmin, dmax = float(delta_range[0]), float(delta_range[1])
                filtered = filtered[
                    filtered["Delta"].fillna(np.nan).apply(lambda x: True if pd.isna(x) == False and (x >= dmin and x <= dmax) else False)
                ]

            # theta
            if theta_exists:
                tmin, tmax = float(theta_range[0]), float(theta_range[1])
                filtered = filtered[filtered["Theta"].fillna(np.nan).apply(lambda x: True if pd.isna(x) == False and (x >= tmin and x <= tmax) else False)]

            # IV
            if "IV" in filtered.columns:
                ivmin, ivmax = float(iv_range[0]), float(iv_range[1])
                filtered = filtered[filtered["IV"].fillna(np.nan).apply(lambda x: True if pd.isna(x) == False and (x >= ivmin and x <= ivmax) else False)]

            # search (safe; handle NaNs)
            if search_query:
                q = str(search_query).strip().lower()
                filtered = filtered[
                    filtered["Contract"].fillna("").str.lower().str.contains(q) |
                    filtered["Strike"].fillna("").astype(str).str.contains(q)
                ]

            # -------------------------
            # Show results & charts
            # -------------------------
            st.write(f"📌 Showing {len(filtered)} contracts (after filters). Full dataset size: {len(full_df)}")
            st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

            # Charts (only if filtered non-empty)
            if not filtered.empty:
                # Delta vs Strike (Streamlit scatter)
                st.subheader("Delta vs Strike")
                # prepare tidy df for the chart (drop NaNs)
                dscatter = filtered.dropna(subset=["Strike", "Delta"])[["Strike", "Delta"]]
                if not dscatter.empty:
                    st.scatter_chart(dscatter.rename(columns={"Strike": "x", "Delta": "y"}), x="x", y="y")
                else:
                    st.info("No Strike+Delta pairs available for scatter chart.")

                # Avg IV vs Expiry
                st.subheader("Average IV by Expiry")
                iv_by_expiry = filtered.dropna(subset=["IV"]).groupby("Expiry")["IV"].mean().reset_index()
                if not iv_by_expiry.empty:
                    iv_by_expiry = iv_by_expiry.set_index("Expiry")
                    st.line_chart(iv_by_expiry)
                else:
                    st.info("No IV data available for line chart.")

            else:
                st.info("No contracts match the selected filters.")

            # -------------------------
            # CSV Download (safe)
            # -------------------------
            csv = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"options_{ticker}.csv",
                mime="text/csv"
            )
