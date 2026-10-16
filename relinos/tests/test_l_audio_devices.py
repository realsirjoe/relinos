from typing import cast
import unittest
from datetime import datetime, timedelta

import requests
from lxml import html
import json

from relinos.parse import JsonType
from relinos.config import serverName

class TestAudioDevices(unittest.TestCase):
    """Some sites check for audio devices so using pulseAudio script makes sure some are returned"""
    def testAudioDevices(self) -> None:
        url = f"https://example.com"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": True,
            "cache": "0s",
            "format": "html",
            "actions": [
                ["actionSleep", "2", ""],
                [
                    "actionExecuteScript", 
                    # puts navigator.mediaDevices.enumerateDevices() output into a html tag
                    """
navigator.mediaDevices.enumerateDevices().then(function(devices){var
  el=document.createElement('pre');el.id='debug_audio_devices';el.style.position='fixed';el.style.top='12px';el.style.right='12px';el.style.zIndex='2147483647';el.style.maxWidth='420px';el.style
  .maxHeight='320px';el.style.overflow='auto';el.style.padding='10px';el.style.background='black';el.style.color='white';el.style.fontSize='12px';el.style.whiteSpace=
  'pre-wrap';document.body.appendChild(el);el.textContent=JSON.stringify(devices,null,2);}).catch(function(err){var
  el=document.createElement('pre');el.textContent='error: '+(err&&err.stack?err.stack:String(err));document.body.appendChild(el);});
                    """, ""],
            ]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text.lower()
        htmlTree = html.fromstring(htmlStr)
        results: list[html.HtmlElement] = cast(list[html.HtmlElement], htmlTree.xpath("//*[@id='debug_audio_devices']"))
        if not results:
            raise AssertionError("TestAudioDevices: Could not find tag debug_audio_devices")

        audioData = json.loads(results[0].text_content())
        if not isinstance(audioData, list):
            raise AssertionError(f"Invalid format for audioData type {type(audioData)}")
        if len(audioData) < 2:
            raise AssertionError(f"Audio input and ouptut len too low = {len(audioData)}")

if __name__ == "__main__":
    unittest.main()
