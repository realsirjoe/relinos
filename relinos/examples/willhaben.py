from typing import cast
from urllib.parse import urlencode

from relinos.config import serverName
from relinos.parse import JsonType
from relinos.normalize import normalizeDict
from relinos.examples.ebay import yahooTodaysExchangeRate

import requests

def searchWillhaben(searchTerm: str) -> list[dict[str, None|bool|int|float|str]]:
    url = "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz/a/zustand-neu-22?" + urlencode({"isNavigation":"true", "srcType": "vertical-search-box", "keyword": searchTerm })

    reqData: JsonType = {
        "url": url,
        "render": True,
        "cache": "60m",
        "actions": [
            ["actionExecuteScript", "window.scrollTo(0, document.body.scrollHeight);", ""],
            ["actionSleep", "2", ""],
        ],
        "format": "json",
        "extraction": {
            "results": {
                "$xpath": "//*[starts-with(@data-testid, 'search-result-entry-header-')]",
                "$list": True,
                "url": { "$xpath": "./@href" },
                "willhabenItemID": { "$xpath": "./@href", "$extract": ".*-(\d+)\/?"},
                "title": { "$xpath": ".//h3" },
                "price": { "$xpath": ".//*[starts-with(@data-testid, 'search-result-entry-price-')]" },
                "description": { "$xpath": ".//*[@class='Box-sc-wfmb7k-0 JRGkQ']" },
                "image": { "$xpath": ".//img/@src" }
            }
        }
    }
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()
    data = resp.json()
    data, err = normalizeDict(data, locale="de-AT")
    if err: raise err

    condition = "New"
    listings = []
    for el in data["results"]:
        try:
            el["condition"] = condition
            if not el.get("price:::amount"): raise Exception("willhaben, could not find price")
            el["price"] = el["price:::amount"]; del el["price:::amount"]
            el["currency"] = el["price:::currency"]; del el["price:::currency"]
            listings.append(el)
        except Exception as e:
            print(f"Failed to parse willhaben listing {str(e)}")

    todaysRates = {}
    for listing in listings:
        currency = listing["currency"]
        if currency not in todaysRates:
            todaysRates[currency] = yahooTodaysExchangeRate(currency, "USD")
        todaysRate = todaysRates[currency]
        listing["priceUSD"] = listing["price"]*todaysRate

    return listings

if __name__ == "__main__":
    results = searchWillhaben("lego set")
    for result in results:
        print(result)
