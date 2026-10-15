# This example searches booking, using many actions
# It is overengineered and is for demonstration of debug mode only
from typing import cast
import json

from relinos.config import serverName
from relinos.parse import JsonType

import requests

def bookingSearch(hotelName: str) -> JsonType:
    reqData: JsonType = {
        "url": "https://www.booking.com",
        "actions": [
            ["actionWaitForAndSelect", "//*[@aria-label=\"Dismiss sign-in info.\"]", "20"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect","//*[@placeholder=\"Where are you going?\"]", "10"],
            ["actionType", hotelName, ""],
            ["actionWaitForAndSelect", "//*[@type='submit']", "10"],
            ["actionClick", "", ""],
            ["actionSleep", "2", ""],
            ["actionSelect", "//*[@aria-label=\"Next month\"]", ""],
            ["actionClick", "", ""],
            ["actionSelect", "//*[@data-date]", ""],
            ["actionFilterAttribute", "data-date", "2026-12-27"],
            ["actionClick", "", ""],
            ["actionSelect", "//*[@data-date]", ""],
            ["actionFilterAttribute", "data-date", "2026-12-29"],
            ["actionClick", "", ""],
            ["actionSelect", '//*[@type="submit"]', ""],
            ["actionFilterIndex", "0", ""],
            ["actionClick", "", ""],
            ["actionSleep", "5", ""],
            ["actionExecuteScript", "document.querySelectorAll('a[target=\"_blank\"]').forEach(a => a.target = '');", ""],
            ["actionSleep", "2", ""],
            ["actionSelect", "//*[@data-testid=\"title\"]", ""],
            ["actionFilterIndex", "0", ""],
            ["actionClick", "", ""],
            ["actionSleep", "5", ""]
        ],
        "render": True,
        "debug": True,
        "includeMeta": True,
    }
    resp = requests.get(serverName + "/get", json=reqData)
    print("Debug at:", resp.headers["x-debug-url"])
    return cast(JsonType, resp.json())

if __name__ == "__main__":
    bookingSearch("Schloss Fuschl")
