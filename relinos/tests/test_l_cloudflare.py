import unittest
import requests

from relinos.config import serverName
from relinos.parse import JsonType

class TestCloudflare(unittest.TestCase):
    def testCloudflarePass(self) -> None:
        url =  "https://www.upwork.com/freelance-jobs/web-design/"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": False,
            "cache": "0s",
            "format": "html",
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text
        anker = "Find the Best Web Designers Jobs"
        with self.subTest():
            if not anker in htmlStr:
                raise AssertionError(f'Cloudflare not passing, could not find site pass anker "{anker}"')

if __name__ == "__main__":
    unittest.main()
