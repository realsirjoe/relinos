import urllib.parse

from relinos.config import serverName

from pydoll.constants import Key
import requests

def searchGithub(searchTerm: str) -> None:
    resp = requests.get(serverName + "/get", json = {
        "url": "https://github.com/search?q=" + urllib.parse.quote_plus(searchTerm),
        "render": True,
        "cache": "60m",
        "actions": [
            ("actionSleep", "1", ""),
            ("actionWaitForAndSelect","(//*[contains(@class, 'search-match')])[1]" ,"10"),
            ("actionClick","",""),
            ("actionWaitForAndSelect","//*[@data-testid='star-button']", "2")
        ],
        "format": "json",
        "extraction": {
            "url": { "$xpath": "//*[@data-tab-item='code']/@href" },
            "stars": { "$xpath": "//*[@data-testid='star-button']", "$extract": "Star(.*) .*"}
        }
    })
    if resp.status_code < 200 or resp.status_code > 299: 
        raise Exception(resp.text)
    print(resp.text)

if __name__ == "__main__":
    searchGithub("realsirjoe/relinos")
