from typing import cast
import unittest
from datetime import datetime, timedelta
import json

from lxml import html
import requests

from relinos.config import serverName
from relinos.parse import JsonType

class TestRecaptcha(unittest.TestCase):
    """ Recaptcha score must be over 0.9 to pass """
    def testRecaptcha(self) -> None:
        url = "https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": False,
            "cache": "0s",
            "format": "html",
            "actions": [
                # for unknown reason needs to be loaded twice in BrowserManager to load
                ["actionGoTo", url, ""], 
                ["actionSleep", "3", ""],
            ]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text.lower()
        htmlTree = html.fromstring(htmlStr)
        recaptchaResponseXPath = "//*[@class='response']"
        results: list[html.HtmlElement] = cast(list[html.HtmlElement], htmlTree.xpath(recaptchaResponseXPath))
        if not results:
            raise AssertionError(f"Invalid TestRecaptcha could not find captcha response on page html")

        captchaResponse = json.loads(results[0].text_content())
        score = captchaResponse["score"]

        with self.subTest():
            if score < 0.9:
                raise AssertionError(f"TestRecaptcha Low captcha score {score}")

if __name__ == "__main__":
    unittest.main()
