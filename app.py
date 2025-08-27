import requests
from requests_oauthlib import OAuth1
import datetime

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
        "chainType": "CALLPUT",  # both calls and puts
        "includeGreeks": "true"
    }

    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()
    return response.json()


def filter_options(data, target_dte: int, target_delta: float):
    """Filter options closest to target DTE and delta"""
    today = datetime.datetime.now().date()

    candidates = []
    if "optionPairs" not in data.get("optionChainResponse", {}):
        return candidates

    for opt in data["optionChainResponse"]["optionPairs"]:
        for contract_type in ["call", "put"]:
            option = opt.get(contract_type)
            if not option:
                continue

            exp_date = datetime.datetime.strptime(option["expiryDate"], "%m/%d/%Y").date()
            dte = (exp_date - today).days
            delta = float(option["greeks"]["delta"])

            # Store with deviation score
            candidates.append({
                "type": contract_type.upper(),
                "symbol": option["optionSymbol"],
                "strike": option["strikePrice"],
                "expDate": option["expiryDate"],
                "dte": dte,
                "delta": delta,
                "theta": option["greeks"]["theta"],
                "vega": option["greeks"]["vega"],
                "gamma": option["greeks"]["gamma"],
                "iv": option["greeks"]["iv"],
                "score": abs(dte - target_dte) + abs(abs(delta) - target_delta)
            })

    # Sort by best match to target DTE + delta
    candidates.sort(key=lambda x: x["score"])
    return candidates


def main():
    while True:
        symbol = input("Enter stock symbol (or 'quit'): ").upper()
        if symbol == "QUIT":
            break
        try:
            dte = int(input("Enter target DTE (e.g., 45): "))
            delta = float(input("Enter target delta (e.g., 0.30): "))

            print(f"\nFetching option chain for {symbol} ...")
            chain_data = get_option_chain(symbol)

            options = filter_options(chain_data, dte, delta)

            if not options:
                print("No options found.\n")
                continue

            print(f"\nTop matches for {symbol} (DTE≈{dte}, Δ≈{delta}):\n")
            for opt in options[:10]:  # show top 10
                print(f"{opt['type']:>4} {opt['symbol']} | "
                      f"Strike: {opt['strike']} | Exp: {opt['expDate']} | "
                      f"DTE: {opt['dte']} | Δ: {opt['delta']:.2f} | "
                      f"Γ: {opt['gamma']:.3f} | Θ: {opt['theta']:.2f} | "
                      f"V: {opt['vega']:.2f} | IV: {opt['iv']:.2f}")

            print("\n")

        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
