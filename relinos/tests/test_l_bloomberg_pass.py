import unittest
import requests

from relinos.config import serverName
from relinos.scraping_api import BrowserManager
from relinos.parse import JsonType

class TestBloomberg(unittest.TestCase):
    '''Bloomberg for some reason detects this is a virtual browser'''
    def testBloomberg(self) -> None:
        url = "https://bloomberg.com"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": False,
            "actions": [["actionSleep", "1", ""]]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text
        htmlStr = htmlStr.lower()

        if "bloomberg terminal demo" not in htmlStr:
            raise AssertionError("Bloomberg blocked the agent")

if __name__ == "__main__":
    unittest.main()
