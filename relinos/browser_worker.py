# Internal REST API
# browser workers perform real browser interactions 

# Linux uses XVFB + Chrome while OSX and Windows render Chrome in an actual GUI
# Every browser can be identified by the workerId + browserNr
# Generally stateless ( 1 request, 1 response ) but interactions can continue by specifying the browser and clearContext = False
# Browser Workers register themselves in a db and send a regular heartbeat, so a master may know which are reachable

from typing import AsyncIterator
import logging
import os
import platform
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
import uuid
import json
from tempfile import mkdtemp
import time

import pydoll.exceptions
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, Response

from relinos.scraping_api import BrowserManager, APIException, ScrapingException, getUserDebugDir, registerBrowser, Action, ActionLoop, browserOSX, browserLinuxXVFB
from relinos.tools import getPublicIP, getPrivateIP

logger = logging.getLogger(__name__)

WORKER_ID_PATH = Path.home() / ".relinos" / "worker-id"
PORT = 18765 # standard browser worker port
BROWSER_POOL_SIZE = int(os.getenv("BROWSER_POOL_SIZE", "4")) # nr of browsers always open waiting for requests
BROWSER_PROXY = os.getenv("BROWSER_PROXY", "")

logger.info(
    f"Browser Worker Settings:\n" 
    f"\tPORT={PORT}\n"
    f"\tBROWSER_POOL_SIZE={BROWSER_POOL_SIZE}\n"
)

browserPoolLock = asyncio.Lock()
browserPool: dict[int, BrowserManager] = {} #TODO since we never delete sessions we should look if memory becomes larger and larger
allBrowsers: set[BrowserManager] = set() # If some browsers are in use when we want to close them they are not in browserPool but still in allBrowsers

workerId: str|None = None
publicAddress = ""
privateAddress = ""
browserType = ""

class ActionModel(BaseModel):
    typ: str
    v0: str = ""
    v1: str = ""

class BrowserRequestModel(BaseModel):
    browserNr: int = -1 # -1 means pick any available
    debug: bool = False
    clearContext: bool = True
    sessionID: str
    url: str
    actions: list[ActionModel] | list[tuple[str, str, str]] = []

def getWorkerID() -> str:
    if WORKER_ID_PATH.exists():
        return WORKER_ID_PATH.read_text().strip()

    WORKER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)

    # last 4 byte will be used for browserNr, workerID + browserNr = browserId ( 32 byte )
    workerID = uuid.uuid4().hex[4:] 
    WORKER_ID_PATH.write_text(workerID)

    return workerID

async def getBrowser(browserNr: int = -1) -> tuple[BrowserManager, int]:
    """
    Gets a browser from the browser pool, 
    If browserNr >= 0 picks specified browser.
    """
    try:
        async with browserPoolLock:
            if browserNr >= 0:
                browser = browserPool[browserNr]
                del browserPool[browserNr]
            else:
                browserNr, browser = browserPool.popitem()
    except KeyError:
        errMsg = "All browsers busy" if browserNr == -1 else f"Browser {browserNr} busy"
        raise HTTPException(status_code=429, detail=errMsg)

    return browser, browserNr

async def releaseBrowser(browser: BrowserManager, browserNr: int) -> None:
    async with browserPoolLock:
        browserPool[browserNr] = browser

async def heartbeat() -> None:
    """
    publicAddress and privateAddress are evaluated on browser worker startup
    If they changed the process must be restarted
    """
    assert isinstance(workerId, str)
    while True:
        try:
            # send heartbeat to master
            for browserNr, browser in enumerate(allBrowsers):
                registerBrowser(workerId, browserNr, publicAddress, privateAddress, browserType)
        except Exception as e:
            logger.error(f"Could not update browsers in db, err: {str(e)}")

        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Sets global variables, starts browsers and adds them to browser pool"""
    global browserPool, allBrowsers, workerId, publicAddress, privateAddress, browserType

    logger.info("App is starting...")
    osName = platform.system().lower()
    if osName == "linux":
        browserType = browserLinuxXVFB
    elif osName == "darwin":
        browserType = browserOSX
    else:
        raise Exception(f"Unsupported operating system {osName}")

    workerId = getWorkerID()
    privateAddress = getPrivateIP()
    publicAddress = getPublicIP()

    try:
        for i in range(BROWSER_POOL_SIZE):
            b = BrowserManager(proxy=BROWSER_PROXY, typ=browserType)
            await b.open()
            async with browserPoolLock:
                allBrowsers.add(b)
                browserPool[i] = b

            logger.info(f"CDP connection opened: {b.browser._connection_handler}")

            registerBrowser(workerId, i, publicAddress, privateAddress, browserType)
    except: 
        await asyncio.gather(
            *(b.close() for b in tuple(allBrowsers)),
            return_exceptions=True,
        )
        raise

    task = asyncio.create_task(heartbeat())

    yield  # app runs here

    logger.info("App is shutting down...")
    await asyncio.gather(
        *(b.close() for b in tuple(allBrowsers)),
        return_exceptions=True,
    )

@asynccontextmanager
async def prepareRequest(clearContext: bool = True, browserNr: int = -1) -> AsyncIterator[BrowserManager]:
    """ 
    Manages browser and error handling
    """
    try:
        browser, browserNr = await getBrowser(browserNr)
        if clearContext: await browser.clearContext()

        yield browser
    except (pydoll.exceptions.PageLoadTimeout, pydoll.exceptions.CommandExecutionTimeout):
        if browser:
            # WEBSOCKET LOCKING if browser seems to be broken we close and create a new one
            # IMPORTANT:, uvicorn or fast api seems to interfere with pydoll's websockets which leads to it getting stuck, 
            # blocking cdp, even restarting websocket didn't fix the issue just killing the process, 
            # closing the browser and creating a new one is a quick fix thats not too costly 
            # since the issue doesn't happen too often
            #TODO Verify: This also means we cannot use pydoll contexts though!!!

            logger.info("Get command timeout, creating new browser")
            await browser.close()
            await browser.open()

        raise HTTPException(status_code=500, detail="Internal Error, try again")
    except HTTPException:
        raise
    except APIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ScrapingException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Uncaught error, type: ", type(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if browser:
            logger.debug("releasing browser")
            if browser.gotoCount >= 50:
                logger.info("Proactivly closing browser and creating a new one (see WEBSOCKET LOCKING)")
                await browser.close()
                await browser.open()

            await releaseBrowser(browser, browserNr)

app = FastAPI(lifespan=lifespan, docs_url=None,redoc_url=None,openapi_url=None)

@app.get("/browser")
async def request(req: BrowserRequestModel) -> Response:
    userDebugDir: str = getUserDebugDir(req.sessionID)
    if req.debug:
        Path(userDebugDir).mkdir(parents=False, exist_ok=True)

    # parsing actions
    actions = []
    for a in req.actions:
        if isinstance(a, tuple):
            action = Action(a[0], a[1], a[2])
        else:
            action = Action(a.typ, a.v0, a.v1)
        actions.append(action)

    async with prepareRequest(req.clearContext, req.browserNr) as browser:
        try:
            tempDir = mkdtemp()
            startTime = int(time.time())
            if req.url: actions = [Action("actionGoTo", req.url, "")] + actions
            if actions: await ActionLoop(browser, actions=actions, startTime=startTime, tempDir=tempDir, debugDir=userDebugDir, debug=req.debug)

            # save page source for inspection
            htmlSrc = await browser.page.page_source_real
            finalUrl = await browser.page.current_url
            jsResult = await browser.page.execute_script("document.contentType")
            contentType = jsResult.get("result", {}).get("result", {}).get("value", "")
        except:
            assert browser != None
            htmlSrc = await browser.page.page_source_real
            if req.debug:
                with open(os.path.join(userDebugDir, "error_site.html"), "w") as f: f.write(htmlSrc)
            raise

        return Response(json.dumps({
            "sessionID": req.sessionID,
            "contentType": contentType,
            "finalUrl": finalUrl,
            "data": htmlSrc
        }), media_type="application/json; charset=utf-8")
