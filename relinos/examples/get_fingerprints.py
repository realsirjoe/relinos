# Gets various fingerprints from browserleaks.com and prints them
from typing import cast 

from relinos.config import serverName
from relinos.parse import JsonType

from lxml import html
import requests

def getCanvasFingerprint() -> str:
    url = "https://browserleaks.com/canvas"
    reqData: JsonType = {
        "url": url, "render": True, "format": "json",
        "extraction": { 
            "canvas_hash": { "$xpath": "//*[@id='canvas-hash']", "$required": True } 
        }
    }
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()

    return str(resp.json()["canvas_hash"])

def getWebRTC() -> bool:
    url = "https://browserleaks.com/webrtc"
    reqData: JsonType = {
        "url": url,
        "render": True,
        "actions": [["actionSleep", "2", ""]]
    }
    htmlSrc = requests.get(serverName + "/get", json=reqData).text
    tree = html.fromstring(htmlSrc)
    results: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//*[@id='rtc-leak']")) 
    hasLeakStr = results[0].text_content().strip()
    if "no leak" in hasLeakStr.lower():
        hasLeak = False
    else:
        hasLeak = True

    return hasLeak

def getWebGLFingerprints() -> str:
    url = "https://browserleaks.com/webgl"
    reqData: JsonType = {
        "url": url,
        "render": True,
        "actions": [["actionSleep", "2", ""]]
    }
    htmlSrc = requests.get(serverName + "/get", json=reqData).text
    tree = html.fromstring(htmlSrc)
    results: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//*[@id='gl-report-hash']"))
    webGLFingerprint: str = results[0].text_content().strip()
    return webGLFingerprint

def getFontFingerprints() -> tuple[str, str]:
    url = "https://browserleaks.com/fonts"
    reqData: JsonType = {
        "url": url,
        "render": True,
        "debug": True,
        "actions": [["actionSleep", "2", ""]]
    }

    htmlSrc = requests.get(serverName + "/get", json=reqData).text
    tree = html.fromstring(htmlSrc)
    results: list[str] = tree.xpath("//*[@id='fonts-metrics-hash']/text()") # type: ignore
    fontFingerprint = results[0].strip()
    results = tree.xpath("//*[@id='fonts-glyphs-hash']/text()") # type: ignore
    fontGlyphFingerprint = results[0].strip()

    return fontFingerprint, fontGlyphFingerprint

def testFingerprints() -> None:
    f: dict[str, str|bool] = {}
    f["hasLeak"] = getWebRTC()
    f["canvasFingerprint"] = getCanvasFingerprint()
    f["webGLFingerprint"] = getWebGLFingerprints()
    f["fontFingerprint"], f["fontGlyphFingerprint"] = getFontFingerprints()
    for k, v in f.items():
        print(k, "\t", v)

if __name__ == "__main__":
    testFingerprints()
