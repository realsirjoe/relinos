import unittest
import time
import asyncio

import requests

from relinos.parse import JsonType

class TestServer(unittest.TestCase):
    def testSharedBrowsersSpeed(self) -> None:
        """ Tests sharedBrowserPool, response time should be quick"""

        start = time.monotonic()
        reqData: JsonType = {
            "url": "https://www.wikipedia.org",
            "debug": False,
            "render": True,
            "cache": "0s",
        }
        resp = requests.get("http://0.0.0.0:8032/get", json=reqData)
        resp.raise_for_status()
        htmlSrc = resp.text

        duration = time.monotonic()-start
        if duration > 5:
            raise AssertionError(f"testSharedBrowsersSpeed took too long {duration:.2f}s")

if __name__ == "__main__":
    unittest.main()
