import unittest
import requests
from lxml import html

from relinos.config import serverName
from relinos.parse import JsonType
from relinos.tools import getPublicIP

class TestWebRTC(unittest.TestCase):
    ''' tests for webrtc leak, test requires a proxy to be set '''
    def testWebRTC(self) -> None:

        url = "https://browserleaks.com/webrtc"
        reqData: JsonType = {
            "url": url,
            "render": True,
            "debug": False,
            "cache": "0s",
            "format": "html",
            "actions": [("actionWaitForAndSelect", "//*[@id='rtc-leak' and @class='']", "20")]
        }
        htmlStr = requests.get(serverName + "/get", json=reqData).text
        tree = html.fromstring(htmlStr)

        # webRTC Support Detection
        results: list[htmlElement] = tree.xpath("//*[@id='rtc-peerconnection']") # type: ignore
        rtcPeerConnection = "true" in results[0].text_content().lower()

        results = tree.xpath("//*[@id='rtc-datachannel']") # type: ignore
        rtcDataChannel = "true" in results[0].text_content().lower()
        if not rtcPeerConnection or not rtcDataChannel:
            raise AssertionError("WebRTC is disabled which looks deviates heavily from standard browsers")

        # proxy needs to be used for this test 
        results = tree.xpath("//*[@id='client-ipv4']//a") # type: ignore
        remoteIPAddress = results[0].text.strip()
        externalIPAddress = getPublicIP()
        if remoteIPAddress == externalIPAddress:
            raise AssertionError("You are not using a proxy, cannot perform webrtc test")
        
        # checks if local ip exposed
        results = tree.xpath("//*[@id='rtc-local']") # type: ignore
        rtcIPLocalAddress = results[0].text.strip() 
        if rtcIPLocalAddress != "-":
            raise AssertionError(f"WebRTC exposes local ip address {rtcIPLocalAddress}")

        results = tree.xpath("//*[@id='rtc-public']") # type: ignore
        # checks if public ip exposed
        if results[0].text_content().strip() == "-":
            raise AssertionError("WebRTC doesn't expose any public ip address which deviates from standard browsers")

        results  = tree.xpath("//*[@id='rtc-public']//a") # type: ignore
        rtcIPAddress = results[0].text.strip()
        if not remoteIPAddress or not rtcIPAddress:
            raise AssertionError("Could not select remoteIPAddress or rtcIPAddress from browserleaks page")

        if remoteIPAddress != rtcIPAddress:
            raise AssertionError(f"WebRTC ip '{rtcIPAddress}' doesn't match your remote ip '{remoteIPAddress}'")

if __name__ == "__main__":
    unittest.main()
