# Searches for available .com domains on namelix, this is how relinos.com was picked
import json
from itertools import combinations

from relinos.config import serverName
from relinos.parse import JsonType

import requests


def getNamelix(searchKeywords: str, maxlen: int = 8) -> list[str]:
    data: JsonType = {
        "url": "https://namelix.com/app",
        "format": "json", "cache": "999y",
        "render": True,
        "actions": [
            ["actionWaitForAndSelect","//input[@id='style-brandable']", "5"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//*[@class='nav-link btn-success']", "5"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//input[@id='radio-random-high']", "5"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//*[@class='nav-link btn-success']", "5"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//*[@id='keywords']", "5"],
            ["actionType", searchKeywords, ""],
            ["actionWaitForAndSelect", "//*[@class='nav-link btn-primary']", "5"],
            ["actionClick", "", ""],
            ["actionWaitForAndSelect", "//*[@class='logo-info']", "20"]
        ],
        "extraction": {
            "generated_names": {
                "$xpath": "//div[contains(@class, 'logo-wrapper')]",
                "$list": True,
                "name": { "$xpath": ".//*[contains(@class, 'description')]" },
                "tld": { "$xpath": ".//*[contains(@class, 'domain-expansion')]" }
            }
        }
    }
    url = serverName + '/get'

    resp = requests.get(url, json=data)
    resp.raise_for_status()
    data = resp.json()

    names = []
    assert isinstance(data, dict)
    generatedNames = data.get("generated_names")
    assert isinstance(generatedNames, list)
    for result in generatedNames:
        assert isinstance(result, dict)
        if result["tld"] == ".com":
            name = result.get("name")
            assert isinstance(name, str)
            names.append(name.replace(" ", "") + ".com") 

    names = [n for n in names if len(n) <= maxlen + 4]
    return names

def findDomains(keywords: list[str]) -> None:
    searches = [" ".join(pair) for pair in combinations(keywords, 2)]

    for combinedKeywords in searches:
        names = getNamelix(combinedKeywords, maxlen=7)
        print(f"Keywords: '{combinedKeywords}'\n{" ".join(names)}\n----")
    
if __name__ == "__main__":
    keywords = [
        "data, vector, semantic, oracle",
        "graph, network, intelligence, arcane",
        "sapient, empirical, insight, forge",
        "crawl, index, sentinel, relic",
        "vector, matrix, cipher, sigil",
        "semantic, search, oracle, vault",
        "data, infer, wisdom, monolith",
        "graph, structure, keystone, arcane",
        "crawl, signal, obelisk, relic",
        "vector, retrieval, sapient, forge",
        "semantic, network, occult, cipher",
        "data, oracle, sorcery, vault",
    ]
    findDomains(keywords)
