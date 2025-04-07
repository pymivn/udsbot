import requests


def get_price_btc(coin: str = "bitcoin") -> dict:
    """
    Fetches the current Bitcoin price in USD, market cap, and 24-hour price change from the CoinGecko API.
    Returns the data as a JSON object.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_market_cap=true&include_24hr_change=true"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx and 5xx)
        data = response.json()

        # Extract Bitcoin price, market cap, and 24-hour change
        btc_data = {
            "price_usd": data[coin]["usd"],
            "market_cap_usd": data[coin]["usd_market_cap"],
            "change_24h_percent": data[coin]["usd_24h_change"],
        }

        return btc_data
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}



data = get_price_btc("bitcoin")
print(data)

print(data["change_24h_percent"])