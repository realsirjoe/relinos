# Searches gov.uk for individual insolvencies
from typing import cast
from urllib.parse import urlencode
import json

from relinos.config import serverName
from relinos.parse import JsonType

import requests
from lxml import html

def individualPage(url: str) -> JsonType:
    reqData: JsonType = {
        "url": url, "render": False, "cache": "999y"
    }
    htmlSrc = requests.get(serverName + "/get", json=reqData).text
    tree = html.fromstring(htmlSrc)
    rows: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//*[@class='govuk-summary-list__row']"))
    item = {}
    for row in rows:
        keys: list[html.HtmlElement] = row.xpath(".//*[@class='govuk-summary-list__key']")
        values: list[html.HtmlElement] = row.xpath(".//*[@class='govuk-summary-list__value']")
        for k, v in list(zip(keys, values)):
            kS = k.text_content().strip()
            vS = v.text_content().strip()

            item[kS] = vS 

    return item

def searchInsolvencies() -> JsonType:
    data = []
    for i in range(1, 40):
        url = "https://www.insolvencydirect.bis.gov.uk/eiir/search-results/QQ/" + str(i)
        reqData: JsonType = {
            "url": url, "render": False, "cache": "50s", "format": "json",
            "extraction": {
                "results": {
                    "$xpath": "//*[@class='govuk-table__row']",
                    "$list": True,
                    "url": { "$xpath": ".//*[@class='govuk-table__cell']//@href" }
                }
            }
        }
        resp = requests.get(serverName + "/get", json=reqData)
        resp.raise_for_status()
        for result in resp.json()["results"]:
            try: 
                data.append(individualPage(result["url"]))
            except: pass

    return data

if __name__ == "__main__":
    searchInsolvencies()
