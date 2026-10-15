import unittest
from datetime import datetime, timedelta

import requests

from relinos.config import serverName
from relinos.parse import JsonType

class TestAkamai(unittest.TestCase):
    def testAkamai(self) -> None:
        departureDate = datetime.now() + timedelta(days=10)
        returnDate = datetime.now() + timedelta(days=13)
        url = "https://www.morganstanley.com/"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": False,
            "cache": "0s",
            "format": "html",
            "actions": [["actionSleep", "5", ""]]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text.lower()
        anker = "investor relations" 
        with self.subTest():
            if "akamai" not in htmlStr:
                raise AssertionError(f"Invalid TestAkamai, the test site doesn't seem to use akamai anymore")
            if not anker in htmlStr:
                raise AssertionError(f'Akamai not passing, could not find site pass anker "{anker}"')

if __name__ == "__main__":
    unittest.main()
