import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time

# =====================
# CONFIG
# =====================
API_KEY = "f0UIbp9U2Ba1MSTnQjess6ZDsuEqygbu"
BASE_URL = "https://api.polygon.io/v3/snapshot/options/"

st.set_page_config(page_title="Options Analyzer", layout="wide")

st.title("📊 Options Analyzer with Greeks (Polygon.io)")

# =====================
# INPUT
# =====================
ticker = st.text_input("Enter stock ticker:", "AAPL").upper()
limit = st.slider("Max results per page (API limit ≤ 1000)", 10, 1000, 500)

if st.button("Fetch Options Data"):
    if not ticker:
        st.error("Please enter a ticker symbol.")
    else:
        progress = st.progress(0)
        all_options = []
        cursor = None
        page = 0

        # =====================
        # FETCH ALL PAGES
        # =====================
        while True:
            url = f"{BASE_URL}{ticker}?limit={limit}&apiKey={API_KEY}"
            if cursor:
                url += f"&cursor={cursor}"

            r = requests.get(url)
            data = r.json()

            if "results" in data:
                all_options.extend(data["results"])
            else:
                break

            cursor = data.get("next_url", None)
            page += 1
            progress.progress(min(page * 0.1, 1.0))  # fake progress update

            if not cursor:
                break

            time.sleep(0.5)  # avoid hitting rate limit

        progress.progress(1.0)
        st.success(f"✅ Retrieved {len(all_options)} option contracts for {ticker}")

        if all_options:
            # =====================
            # PROCESS INTO DATAFRAME
            # =====================
            df = pd.DataFrame([
                {
                    "Contract": opt["details"]["ticker"],
                    "Type": opt["details"]["contract_type"],
                    "Strike": opt["details"]["strike_price"],
                    "Expiry": opt["details"]["expiration_date"],
                    "Delta": opt.get("greeks", {}).get("delta"),
                    "Gamma": opt.get("greeks", {}).get("gamma"),
                    "Theta": opt.get("greeks", {}).get("theta"),
                    "Vega": opt.get("greeks", {}).get("vega"),
                    "IV": opt.get("implied_volatility"),
                    "OI": opt.get("open_interest"),
                    "Last Price": opt["day"].get("close"),
                    "Underlying": opt["underlying_asset"]["ticker"],
                }
                for opt in all_options
            ])

            # =====================
            # FILTERS
            # =====================
            expiry_options = sorted(df["Expiry"].unique())
            expiry_filter = st.multiselect("Filter by expiry:", expiry_options, default=expiry_options)

            type_filter = st.multiselect("Filter by contract type:", ["call", "put"], default=["call", "put"])

            strike_min, strike_max = st.slider(
                "Strike range:", 
                float(df["Strike"].min()), 
                float(df["Strike"].max()), 
                (float(df["Strike"].min()), float(df["Strike"].max()))
            )

            filtered_df = df[
                (df["Expiry"].isin(expiry_filter)) &
                (df["Type"].isin(type_filter)) &
                (df["Strike"].between(strike_min, strike_max))
            ]

            st.write(f"📌 Showing {len(filtered_df)} contracts after filtering")
            st.dataframe(filtered_df, use_container_width=True)

            # =====================
            # PLOTS
            # =====================
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Delta vs Strike")
                fig, ax = plt.subplots()
                ax.scatter(filtered_df["Strike"], filtered_df["Delta"], alpha=0.6)
                ax.set_xlabel("Strike")
                ax.set_ylabel("Delta")
                ax.set_title("Delta vs Strike")
                st.pyplot(fig)

            with col2:
                st.subheader("Average IV by Expiry")
                iv_by_expiry = filtered_df.groupby("Expiry")["IV"].mean().reset_index()
                fig, ax = plt.subplots()
                ax.plot(iv_by_expiry["Expiry"], iv_by_expiry["IV"], marker="o")
                ax.set_xlabel("Expiry")
                ax.set_ylabel("Average IV")
                ax.set_title("Average Implied Volatility by Expiry")
                plt.xticks(rotation=45)
                st.pyplot(fig)

            # =====================
            # DOWNLOAD CSV
            # =====================
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="options_data.csv",
                mime="text/csv"
            )
        else:
            st.warning("No options data found.")
