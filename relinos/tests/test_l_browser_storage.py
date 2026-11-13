from typing import Any
import unittest
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse

from relinos.config import serverName

import requests

testServerUrl: str = ""

cookiesTestSite = """
<html>
  <body>
    <h1>Cookie persistence test</h1>
    <p>Origin: <code id="origin"></code></p>
    <p id="status"></p>
    <p>Stored value: <code id="value"></code></p>

    <script>
      const value = document.cookie.match(/(?:^|; )value=([^;]*)/)?.[1];
      const created = value === undefined;
      const storedValue = value ?? crypto.randomUUID();

      document.cookie = `value=${storedValue}; path=/; SameSite=Lax`;
      document.querySelector("#origin").textContent = location.origin;
      document.querySelector("#status").textContent = created ? "Created a random cookie value." : "Reused the existing cookie value.";
      document.querySelector("#value").textContent = storedValue;
    </script>
  </body>
</html>
"""

localStorageTestSite = """
<html>
  <body>
    <h1>localStorage persistence test</h1>
    <p>Origin: <code id="origin"></code></p>
    <p id="status"></p>
    <p>Stored value: <code id="value"></code></p>

    <script>
      const value = localStorage.getItem("value");
      const created = value === null;
      const storedValue = value ?? crypto.randomUUID();

      localStorage.setItem("value", storedValue);
      document.querySelector("#origin").textContent = location.origin;
      document.querySelector("#status").textContent = created ? "Created a random localStorage value." : "Reused the existing localStorage value.";
      document.querySelector("#value").textContent = storedValue;
    </script>
  </body>
</html>
"""

indexedDBTestSite = """
<html>
  <body>
    <h1>IndexedDB persistence test</h1>
    <p>Origin: <code id="origin"></code></p>
    <p id="status"></p>
    <p>Stored value: <code id="value"></code></p>
          
    <script>
    (async () => {
        const wait = request => new Promise((resolve, reject) =>
        (request.onsuccess = () => resolve(request.result), request.onerror = () => reject(request.error)));

        const open = indexedDB.open("testDB", 1);
        open.onupgradeneeded = () => open.result.createObjectStore("testStore");
        const db = await wait(open);
        const store = db.transaction("testStore", "readwrite").objectStore("testStore");
        let value = await wait(store.get("value"));
        const created = value === undefined;
        value ??= crypto.randomUUID();
        await wait(store.put(value, "value"));
        db.close();
        
        document.querySelector("#origin").textContent = location.origin;
        document.querySelector("#status").textContent = created ? "Created a random IndexedDB value." : "Reused the existing IndexedDB value.";
        document.querySelector("#value").textContent = value;
    })().catch(error => {
        document.querySelector("#status").textContent = `IndexedDB error: ${error.message}`;
    });
    </script>
  </body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    pages = {
        "/cookies": cookiesTestSite,
        "/localstorage": localStorageTestSite,
        "/indexeddb": indexedDBTestSite,
    }
    def do_GET(self) -> None:
        html = self.pages.get(urlparse(self.path).path)
        if html is None: self.send_error(404); return
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: Any) -> None: 
        pass  # suppress test-server logs

class TestBrowserStorage(unittest.TestCase):
    """ tests if passing sessionID uses the previous requests cookies, localStorage and indexedDB """
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

    def testCookies(self) -> None:
        resp = requests.post(serverName + "/session")
        sessionID = json.loads(resp.text)["sessionID"]

        # calling twice with the same sessionID should find the same set cookie and match
        values = []
        for i in range(2):
            data = {
                "url": testServerUrl + "/cookies",
                "cache": "0d",
                "render": True, "sessionID": sessionID,
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            cookie = json.loads(resp.text).get("value", "")
            self.assertNotEqual(cookie, "")
            values.append(cookie)
        self.assertEqual(values[0], values[1])

        # calling twice without sessionID should find different cookies 
        values = []
        for i in range(2):
            data = {
                "url": testServerUrl + "/cookies",
                "cache": "0d",
                "render": True, 
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            cookie = json.loads(resp.text).get("value", "")
            self.assertNotEqual(cookie, "")
            values.append(cookie)
        self.assertNotEqual(values[0], values[1])

    def testLocalStorage(self) -> None:
        resp = requests.post(serverName + "/session")
        sessionID = json.loads(resp.text)["sessionID"]

        # calling twice with the same sessionID should find the same localStorage value and match
        values = []
        for i in range(2):
            data = {
                "url": testServerUrl + "/localstorage",
                "cache": "0d",
                "render": True, "sessionID": sessionID,
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            localStorage = json.loads(resp.text).get("value", "")
            self.assertNotEqual(localStorage, "")
            values.append(localStorage)

        self.assertEqual(values[0], values[1])

        # calling twice without sessionID should find different localStorage values 
        values = []
        for i in range(2):
            data = {
                "url": testServerUrl + "/localstorage",
                "cache": "0d",
                "render": True,
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            localStorage = json.loads(resp.text).get("value", "")
            self.assertNotEqual(localStorage, "")
            values.append(localStorage)

        self.assertNotEqual(values[0], values[1])

    def testIndexedDB(self) -> None:
        resp = requests.post(serverName + "/session")
        sessionID = json.loads(resp.text)["sessionID"]

        # calling twice with the same sessionID should find the same indexedDB value and match
        values = []
        for _ in range(2):
            data = {
                "url": testServerUrl + "/indexeddb",
                "cache": "0s",
                "render": True, "sessionID": sessionID,
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            indexedDBValue = json.loads(resp.text).get("value", "")
            self.assertNotEqual(indexedDBValue, "")
            values.append(indexedDBValue)
        self.assertEqual(values[0], values[1])

        values = []
        for _ in range(2):
            data = {
                "url": testServerUrl + "/indexeddb",
                "cache": "0s",
                "render": True,
                "format": "json", "extraction": {
                    "value": { "$xpath": "//*[@id='value']" }
                }
            }
            resp = requests.get(serverName + "/get", json=data)
            indexedDBValue = json.loads(resp.text).get("value", "")
            self.assertNotEqual(indexedDBValue, "")
            values.append(indexedDBValue)
        self.assertNotEqual(values[0], values[1])
        
if __name__ == "__main__":
    unittest.main()
