import unittest
from datetime import datetime, timedelta

import requests

from relinos.config import serverName
from relinos.parse import JsonType

class TestDatadome(unittest.TestCase):
    def testDatadome(self) -> None:
        url = "https://grainger.com/"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": True,
            "cache": "0s",
            "format": "html",
            "actions": [["actionSleep", "10", ""]]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text.lower()
        htmlStr = htmlStr.lower()
        if "all products" not in htmlStr or "bulk order" not in htmlStr:
            raise AssertionError("Could not get passed datadome")

if __name__ == "__main__":
    unittest.main()
