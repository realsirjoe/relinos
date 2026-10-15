from typing import cast
from urllib.parse import urlencode
import json

from relinos.config import serverName
from relinos.parse import parseHtml, getCoverageScore, JsonType

import requests

def searchVinted(searchTerm: str) -> list[dict[str, JsonType]]:
    def parseVintedItems(htmlSrc: str) -> list[dict[str, JsonType]]:
        xpathschema = {
            "listings": {
                "$xpath": '//*[@data-testid="grid-item"]',
                "$list": True,
                "price": { "$xpath": './/*[@data-testid="total-combined-price"]', "$extract": r"\$(\d+(?:\.\d{2})?)" },
                "vintedItemID": { "$xpath": './/*[contains(@class, "new-item-box__container")]/@data-testid', "$pattern": 'product-item-id.*', "$extract": 'product-item-id-([0-9]+)' },
                "title": { "$xpath": './/*[contains(@class, "new-item-box__description")]' },
                "description": { "$xpath": '(.//*[contains(@class, "new-item-box__description")])[2]'},
                "image": { "$xpath": './/*[@class="web_ui__Image__content"]/@src' }
            }
        }
        rawListings, err = parseHtml(htmlSrc, json.dumps(xpathschema))
        if err: raise err
        assert isinstance(rawListings, dict)
        rawListings = rawListings["listings"]
        assert isinstance(rawListings, list)

        # prevously we could extract all elements covScore = 1
        covScore, _ =  getCoverageScore(rawListings) 
        if covScore < 1: raise Exception("Could not extract all elements")

        listings = []
        for l in rawListings:
            assert isinstance(l, dict)
            vintedItemID = l["vintedItemID"]
            assert isinstance(vintedItemID, str)
            l["condition"] = cast(str, l["description"]).split("·")[-1].strip()
            l["url"] = "https://www.vinted.com/items/" + vintedItemID 

            listings.append(l)

        return listings

    searchUrl = "https://www.vinted.com/catalog?" + urlencode({"search_text": searchTerm, "order": "newest_first", "page": "1"})
    reqData: JsonType = {"url": searchUrl, "render": False, "debug": False, "cache": "1d"}
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()
    htmlSrc = resp.text
    return parseVintedItems(htmlSrc)

if __name__ == "__main__": 
    listings = searchVinted("lego")
    for listing in listings:
        print(listing)
