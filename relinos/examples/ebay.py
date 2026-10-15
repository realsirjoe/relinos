# Searches ebay and returns structured results
from urllib.parse import urlencode

from relinos.config import serverName
from relinos.parse import parseHtml, getCoverageScore, JsonType
from relinos.normalize import normalizeDict

import requests

def yahooTodaysExchangeRate(curr1: str, curr2: str, cache: str = "0s") -> float:
    currStr = curr1 + curr2 + "=X"
    url = f"https://finance.yahoo.com/quote/{currStr}/history/"
    reqData: JsonType = { 
        "render": False, "cache": cache, "url": url, "format": "json",
        "extraction": { 
            "todaysRate": { 
                "$xpath": "//*[@data-testid='history-table']//tbody/tr[1]/td[2]", 
                "$required": True, "$transform": "float" 
            }
        }
    }
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()
    return float(resp.json()["todaysRate"])

def searchEbay(searchTerm: str) -> list[dict[str, str|int|float|bool|None]]:
    url = "https://www.ebay.com/sch/i.html?" + urlencode({"_nkw": searchTerm, "_sacat": "0", "_from": "R40", "_ipg": "120", "_sop": "10", "rt": "nc", "LH_BIN": "1"})

    reqData: JsonType = {
        "url": "https://www.ebay.com",
        "render": True,
        "cache": "1d",
        "actions": [["actionSleep", "2", ""], ["actionGoTo", url, ""], ["actionSleep", "3", ""]],
        "format": "json",
        "extraction": {
            "listings": {
                "$xpath": "//*[contains(@class, 'srp-results')]/li",
                "$list": True,
                "price": { "$xpath": ".//*[contains(@class, 's-card__price')]" },
                "title": { "$xpath": ".//*[contains(@class, 's-card__title')]/span" },
                "condition": { "$xpath": ".//*[@class='s-card__subtitle']" },
                "image": { "$xpath": ".//*[contains(@class, 's-card__image')]/@src" },
                "url": { "$xpath": ".//*[contains(@class, 's-card__link')]/@href", r"$extract": "(.*)\?.*" }, 
                "ebayItemID": { "$xpath": ".//*[contains(@class, 's-card__link')]/@href", "$extract": ".*/itm/([0-9]+).*" }, 
            }
        }
    }
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()
    rawListings = resp.json()["listings"]
    rawListings, err = normalizeDict(rawListings, locale="en-US")
    if err: raise err
    
    listings = []
    for l in rawListings:
        if not l["ebayItemID"]: continue
        try:
            l["currency"] = l["price:::currency"]; del l["price:::currency"]
            l["price"] = l["price:::amount"]; del l["price:::amount"]
            if not l["price"]: raise Exception("Could not locate price")

            listings.append(l)
        except Exception as e:
            print(f"Could not parse ebay item: {str(e)}")

    todaysRates = {"USD": 1.0}
    for listing in listings:
        currency = listing["currency"]
        if currency not in todaysRates:
            todaysRates[currency] = yahooTodaysExchangeRate(currency, "USD", cache="12h")
        todaysRate = todaysRates[currency]
        listing["priceUSD"] = listing["price"]*todaysRate
        print(listing)

    return listings

if __name__ == "__main__":
    print("FX USD to EUR", yahooTodaysExchangeRate("USD", "EUR", "12h"))
    print("Ebay Search results")
    searchEbay("lego")
