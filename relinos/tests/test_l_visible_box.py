import unittest
import re
import requests

from urllib.parse import urlencode

from relinos.config import serverName
from relinos.parse import JsonType

class TestTypeIntoBrowser(unittest.TestCase):
    def testTypeIntoBrowser(self) -> None:
        """ 
        This test failed to type into an element, previously when the chrome window was not a normal 1920x1080
        """
    
        url = "https://mueller.at"
        searchTerm = "playmobile"

        reqData: JsonType = {
            "url": url, "render": True, "debug": True, "cache": "0s",
            "actions": [
                ["actionWaitForAndSelect", '//*[@id="accept"]', "60"],
                ["actionClick", "", ""],
                ["actionWaitForAndSelect", "//*[@id='586d0c4c-d2c6-4d32-9858-514ea76af805-searchbar']", "2"],
                ["actionType", searchTerm, ""],
                ["actionWaitForAndSelect", '//*[@data-track-id="searchButton"]', "2"],
                ["actionFilterIndex", "0", ""],
                ["actionClick", "", ""],
                ["actionKeyboardEnter", "", ""],
                ["actionSleep", "7", ""],
            ]
        }
        resp = requests.get(serverName + "/get", json=reqData)
        resp.raise_for_status()

if __name__ == "__main__":
    unittest.main()
