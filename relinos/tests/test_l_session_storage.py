import unittest

from relinos.config import serverName

import requests
import json

class TestSessionStorage(unittest.TestCase):
    """ tests if passing sessionID uses the previous requests storage """
    def testCookies(self) -> None:
        resp = requests.post(serverName + "/session")
        sessionID = json.loads(resp.text)["sessionID"]

        # setting cookie
        data = {
            "url": "https://httpbin.org/cookies/set?test=12345",
            "render": True, "sessionID": sessionID
        }
        resp = requests.get(serverName + "/get", json=data)
        sessionID = resp.headers.get("x-session-id")

        # verifying cookie present
        data = {
            "url": "https://httpbin.org/cookies",
            "render": True,
            "sessionID": sessionID,
            "format": "json",
            "extraction": { "json": { "$xpath": "//html" } }
        }
        resp = requests.get(serverName + "/get", json=data)
        cookieData = json.loads(json.loads(resp.text)["json"])
        assert cookieData.get("cookies", {}).get("test", "") == "12345"
        
if __name__ == "__main__":
    unittest.main()
