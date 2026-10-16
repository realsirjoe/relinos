# Searches google and returns structured results
from typing import cast
import json
import time

from relinos.config import serverName
from relinos.parse import JsonType

import requests

def google(searchTerm: str, pages: int = 1, cache: str = "10m") -> tuple[JsonType, Exception|None]:

    reqData: JsonType = {
        "url": "https://www.google.com",
        "render": True,
        "debug": False,
        "cache": cache,
        "actions": [
            ["actionSelect", "//textarea[@name='q']", ""], ["actionType", searchTerm, ""], 
            ["actionKeyboardEnter", "", ""], 
            ["actionSleep", "2", ""]
        ],
        "format": "json",
        "extraction": {
            "results": {
                "$xpath": "//*[contains(@class, 'Ww4FFb')]",
                "$list": True,
                "domain": {
                    "$xpath": ".//*[contains(@class, 'CA5RN')]//cite/text()",
                    "$extract": "(?:https?://)?(.*)"
                },
                "url": {
                    "$xpath": ".//*[contains(@class, 'zReHs')]/@href",
                    "$pattern": "(https?://)?.*"
                },
                "title": { "$xpath": ".//h3" },
                "description": { "$xpath": ".//*[contains(@class, 'VwiC3b yXK7lf p4wth r025kc Hdw6tb')]" }
            },
            "people_also_search_for": {
                "$xpath": "//*[@class='ngTNl ggLgoc']",
                "$list": True 
            },
            "questions": {
                "$xpath": "//*[contains(@class, 'wQiwMc')]",
                "$list": True,
                "question": { "$xpath": ".//*[contains(@class, 'CSkcDe')]" },
                "answer": {
                    "$xpath": ".//*[contains(@class, 'hICk5e')]",
                    "$transform": "markdown"
                }
            }
        },
        "pagination": ["//*[@id='pnnext']", pages]
    }
    resp = requests.get(serverName + "/get", json=reqData)
    try:
        resp.raise_for_status()
    except Exception as e:
        return None, e
    return resp.json(), None

if __name__ == "__main__":
    iterations = 5
    errCount = 0
    for i in range(iterations):
        data, err = google("Charles Dickens", 2, cache="0s")
        assert type(data) == dict
        if err or not data.get("results") or len(cast(list[JsonType], data["results"])) < 5:
            errCount += 1
        else:
            print(data["results"])
        time.sleep(3)
    errRatio = errCount/iterations
    if errRatio > 0.4:
        raise AssertionError(f"Error Ratio {errRatio} to high, iterations: {iterations}")
