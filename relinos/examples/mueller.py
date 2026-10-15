from relinos.config import serverName
from relinos.parse import JsonType

import requests

def searchMueller(searchTerm: str) -> str:
    url = "https://www.mueller.at"

    reqData: JsonType = {
        "url": url, "render": True, "debug": True, "cache": "0s", "format": "md",
        "actions": [
            ["actionWaitForAndSelect", '//*[@id="accept"]', "60"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//*[@id='586d0c4c-d2c6-4d32-9858-514ea76af805-searchbar']", "2"],
            ["actionType", searchTerm, ""],
            ["actionWaitForAndSelect", "(//*[@title='Suchen'])[1]", "2"],
            ["actionClick", "", ""],
            ["actionSleep", "5", ""],
        ]
    }
    resp = requests.get(serverName + "/get", json=reqData)
    if not resp.ok:
        print(resp.text)
        resp.raise_for_status()

    print(resp.text)
    return resp.text

if __name__ == "__main__": 
    searchMueller("makeup")
