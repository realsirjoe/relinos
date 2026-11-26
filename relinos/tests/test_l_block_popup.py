import unittest
import asyncio
import time
from tempfile import mkdtemp
from urllib.parse import urlparse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from relinos.scraping_api import BrowserManager, browserOSX, ActionLoop, Action

testServerUrl = ""

blankPopupSite = """
<html>
    <body>
        <a href="/" target="_blank">Open popup</a>
    </body>
</html>
"""

windowOpenPopupSite = """
<html>
    <body>
        <a id="popup"
            onclick="window.open('/', '_blank')">
            Open popup
        </a>
    </body>
</html>
"""

formBlankPopupSite = """
<html>
    <body>
        <form action="/" target="_blank">
            <button type="submit">Open popup</button>
        </form>
    </body>
</html>
"""

formSubmitPopupSite = """
<html>
    <form id="form" action="/" target="_blank"></form>
    <button onclick="document.getElementById('form').submit()">
    Open popup
    </button>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    pages = {
        "/": "<html><head></head><body>Final Destination</body></html>",
        "/blank": blankPopupSite,
        "/windowOpen": windowOpenPopupSite,
        "/formBlank": formBlankPopupSite,
        "/formSubmit": formSubmitPopupSite
    }
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        html = self.pages.get(parsed.path)
        if html is None: self.send_error(404); return
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: Any) -> None: 
        pass  # suppress test-server logs

class TestBlockPopup(unittest.IsolatedAsyncioTestCase):
    server: ThreadingHTTPServer
    thread: Thread

    @classmethod
    def setUpClass(cls) -> None:
        global testServerUrl
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        testServerUrl = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    async def blockPopupTest(self, endpoint: str, selector: str) -> None:
        global testServerUrl
        b = BrowserManager(typ=browserOSX)
        await b.open()

        try:
            actions = [
                Action("actionGoTo", testServerUrl + endpoint, ""),
                Action("actionWaitForAndSelect", selector, "3"),
                Action("actionClick", "", ""),
            ]
            await ActionLoop(b, actions, time.time(), tempDir = mkdtemp(), debugDir = "", debug = False)
            tabs = await b.browser.get_opened_tabs()
            self.assertEqual(len(tabs), 1)

            # it should still redirect in current tab
            htmlSrc = await b.page.page_source
            self.assertEqual("<html><head></head><body>Final Destination</body></html>", htmlSrc)
        finally:
            await b.close()

    async def testBlank(self) -> None:
        await self.blockPopupTest("/blank", "(//a)[1]")

    async def testWindowOpen(self) -> None:
        await self.blockPopupTest("/windowOpen", "(//a)[1]")

    async def testFormBlank(self) -> None:
        await self.blockPopupTest("/formBlank", "(//button)[1]")

    async def testFormSubmit(self) -> None:
        await self.blockPopupTest("/formSubmit", "(//button)[1]")

if __name__ == "__main__":
    unittest.main()
