from __future__ import annotations
from typing import Any, Callable, Optional, cast
import asyncio
import os
from pathlib import Path
import hashlib
import uuid
import subprocess
import shutil
import json
import urllib
import threading
import time
import re
import sqlite3
from datetime import datetime
from functools import partial

from pydoll.constants import PageLoadState
from pydoll.browser import Chrome
from pydoll.browser.tab import Tab
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import InputCommands
from pydoll.protocol.fetch.events import FetchEvent
from pydoll.protocol.network.types import ResourceType
from pydoll.protocol.base import Command
from pydoll.protocol.input.types import KeyEventType
from pydoll.elements.web_element import WebElement

from curl_cffi import requests
from curl_cffi.requests import AsyncSession
import requests as requestsStd
from lxml import html
from fastapi import HTTPException

from relinos.config import dbPath, storageDirPath, cacheDirPath, cacheDBPath, debugDirPath, dumpDirPath 
from relinos.tools import createPdfFromFolder, addCaption, addRedBorder, createHtmlPagesViewer, generateSignature, serialize, deserialize, int_number_re, float_number_re, writeFileAtomic
from relinos.parse import generateUrlName, parseHtml, JsonType
from relinos.normalize import removeEmptyFields, fuseData
from relinos.markdown import htmlToMarkdown

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("pydoll").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

Path(storageDirPath).mkdir(exist_ok=True)
Path(cacheDirPath).mkdir(exist_ok=True)
Path(debugDirPath).mkdir(exist_ok=True)
Path(dumpDirPath).mkdir(exist_ok=True)

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()

def getChrome(displayNumber: str, userDataDir: str, proxy: str = "") -> Chrome:
    options = ChromiumOptions()
    #TODO Parametrize binary_location above
    #options.binary_location = "/custom_chrome_path"
    # likely loads faster
    options.page_load_state = PageLoadState.INTERACTIVE
    args = []
    args.append('--no-sandbox')
    args.append('--window-size=1920,1080') # matching XVFB screen size
    args.append('--disable-dev-shm-usage')
    args.append('--disable-gcm-registration')
    args.append(f'--user-data-dir={userDataDir}')
    args.append("--use-fake-device-for-media-stream")

    if displayNumber: 
        args.append(f'--display={displayNumber}')

    if proxy: 
        args.append(f'--proxy-server={proxy}')

    for arg in args:
        options.add_argument(arg)

    return Chrome(options=options)

class APIException(Exception):
    pass

class ScrapingException(Exception):
    pass

actionSleep =            "actionSleep"
actionClick =            "actionClick"
actionType =             "actionType"
actionKeyboardEnter =    "actionKeyboardEnter"
actionSelect =           "actionSelect"
actionWaitForAndSelect = "actionWaitForAndSelect"
actionFilterText =       "actionFilterText"
actionFilterAttribute =  "actionFilterAttribute"
actionFilterIndex =      "actionFilterIndex"
actionExecuteScript =    "actionExecuteScript"
actionGoTo =             "actionGoTo"

class Action:
    typ: str
    v0: str
    v1: str
    def __init__(self, typ: str, v0: str="", v1: str=""):
        self.typ = typ
        self.v0 = v0
        self.v1 = v1

class Pagination:
    nextPageXPath: str
    maxPages: int
    clickDelaySeconds: int

    def __init__(self, nextPageXPath: str, maxPages: int, clickDelaySeconds: int = 3):
        self.nextPageXPath = nextPageXPath
        self.maxPages = maxPages
        self.clickDelaySeconds = clickDelaySeconds

class ExtractionMeta:
    """ Metadata on the extraction """
    name: str
    description: str
    domain: str
    url: str 
    keyCount: int
    keyCoverage: float
    coverageScore: float

    def __init__(self, name: str, description: str, domain: str, url: str, keyCount: int, keyCoverage: float, coverageScore: float):
        self.name = name 
        self.description = description
        self.domain = domain
        self.url = url
        self.keyCount = keyCount
        self.keyCoverage = keyCoverage
        self.coverageScore = coverageScore
        # prefixed to avoid hash collisions with routine names
        self.id = sha1("e_" + self.name)

        # simplified url that can possibly match request to correct extraction
        self.urlName = generateUrlName(self.url)

transformMap = {
    "url_quote": urllib.parse.quote,
    "url_query_quote": urllib.parse.quote_plus
}

kindInt = "int"
kindFloat = "float"
kindDate = "date"
kindStr = "str"

def isValidDate(v: str) -> bool:
    if len(v) != 10: return False
    try: datetime.strptime(v, "%Y-%m-%d"); return True
    except ValueError: return False

kindMap: dict[str, Callable[[Any], bool]]  = {
    kindInt: lambda v: isinstance(v, int) or int_number_re.fullmatch(v) != None,
    kindFloat: lambda v: isinstance(v, float) or float_number_re.fullmatch(v) != None,
    kindDate: lambda v: isValidDate(v),
    kindStr: lambda v: isinstance(v, str)
}

def setNestedAttr(obj: Any, path: str, value: Any, startIndex: int=-1, endIndex: int=-1) -> bool:
    """
    sets nested attribute in JSON-like objects
    can walk lists and dicts

    example path: posts.2.comments.0.author

    If startIndex or endIndex are specified, the existing string is modified by
    replacing the slice [startIndex:endIndex] with `value`.

    startIndex is inclusive, -1 means nothing before
    endIndex is exclusive, -1 means nothing after

    Examples:
        "hello", value="peter", startIndex=2, endIndex=3
        -> "hepeterlo"    # replaces "l"

        "hello", value="peter", startIndex=-1, endIndex=0
        -> "peterhello"   # insert before first character

        "hello", value="peter", startIndex=5, endIndex=5
        -> "hellopeter"   # append

    return success
    """
    parts = path.split(".")

    try:
        for part in parts[:-1]:
            if isinstance(obj, list): 
                obj = obj[int(part)]
            else: 
                obj = obj[part]

        last:int|str = parts[-1]
        if isinstance(obj, list):
            last = int(last)

        prefix = ""
        suffix = ""
        if startIndex >= 0:
            prefix = obj[last][:startIndex]
        if endIndex >= 0:
            suffix = obj[last][endIndex:]

        obj[last] = prefix + value + suffix
        return True
    except:
        return False

class Patch:
    keypath: str
    start: int
    end: int
    transform: str

    def __init__(self, keypath: str, start: int = -1, end: int = -1, transform: str = ""):
        """
        A patch describes an incision of a transformed value

        keypath: describes where to insert in json e.g. person.posts.2.comments.1.text
        start:      repacing at startIndex -1 means starts at beginning, start is inclusive
        end:        replacing at endIndex -1 means ends at the end, end is exclusive, see setNestedAttr
        transform: to map the parameter see transformMap
        """
        self.keypath = keypath
        self.start = start
        self.end = end
        self.transform = transform

class RoutineParam:
    name: str
    description: str
    patches: list[Patch]
    default: str
    kind: str

    def __init__(self, name: str, description: str, patches: list[Patch], default: str = "", kind: str = kindStr):
        '''
        RoutineParam's monkeypatch the Routine on .do(), see Patch
        kind checks if the actual param is int like, float like, ...

        Patch start and end positions refer to the initial attribute positions, 
        which means if a patch changes an attributes length by replacing something the other patches will be adjusted
        see Routine.do
        '''
        self.name = name
        self.description = description

        self.patches = patches 
        self.default = default
        self.kind = kind

formatHTML = "html"
formatMD = "md"
formatJSON = "json"
supportedFormats = {formatHTML, formatMD, formatJSON}

class Routine:
    name: str
    description: str
    params: list[RoutineParam]
    url: str
    render: bool
    actions: list[Action]
    pagination: Pagination | None
    extraction: str|dict[str, JsonType]

    def __init__(
            self, name: str, description: str, params: list[RoutineParam], 
            url: str, render: bool, actions: list[Action], pagination: Pagination | None, 
            extraction: str|dict[str, JsonType] = "",
        ):
        """
        Routines are reusable functions that interact with the web
          can take input
          can return data in various formats like html, md and json
        """
        # names are case insensitive
        self.name = name.lower()
        self.description = description

        # prefix to avoid collisions with extractions or other possible future types in object directory
        self.id = sha1("r_" + self.name)

        # checks if patches use valid top level keys 
        patchKeypaths = [m.keypath for p in params for m in p.patches]
        topLevelKeys = {m.split(".")[0] for m in patchKeypaths}
        supportedTopLevelKeys = ["url", "actions", "pagination"]
        for key in topLevelKeys:
            if key not in supportedTopLevelKeys:
                raise ValueError(f"Unsupported key can only modify {','.join(supportedTopLevelKeys)}")

        # checks for duplicate params
        paramNames = [p.name for p in params]
        if len(paramNames) != len(set(paramNames)):
            raise ValueError("Duplicate names in param names")

        self.params = params
        self.paramsMap = {p.name: p for p in params}

        self.url = url
        self.actions = actions
        self.pagination = pagination
        self.render = render

        self.extraction = extraction

    def helpMessage(self) -> str:
        s = f"{self.name}\n"
        for p in self.paramsMap.values():
            s += f"    {p.name}"
            if p.description: s += f": {p.description}"
            s += "\n"
        return s

    def shortHelpMessage(self) -> str:
        return f'{self.name}({",".join([p.name + ("?" if p.default else "") for p in self.paramsMap.values()])})'

    def patch(self, params: dict[str, str]) -> Routine:
        try:
            serializedRoutine = serialize(self)
        except:
            raise APIException("Internal Error, Malformed routine")

        adjustments: dict[str, int] = {}
        for k in self.paramsMap.keys():
            for p in self.paramsMap[k].patches:
                value = params[k]
                if p.transform: 
                    if p.transform not in transformMap:
                        raise APIException(f"Unknown transform '{p.transform}' for param '{p.keypath}'")
                    value = transformMap[p.transform](value)
                adjustment = adjustments.get(p.keypath, 0)
                # danger if value is a reference type
                success = setNestedAttr(serializedRoutine, p.keypath, value, p.start+adjustment, p.end+adjustment)
                if not success: 
                    raise APIException(f"Unable to set routine attribute with keypath '{p.keypath}'")

                # start and end patch positions are based on an attributes initial length 
                # so we need to adjust after changing an attribute
                oldLen = p.end - p.start
                newLen = len(value)
                adjustments[p.keypath] = adjustments.get(p.keypath, 0) + (newLen - oldLen)
        try:
            routineCopy: Routine = deserialize(Routine, serializedRoutine)
        except:
            raise APIException("Internal Error, Malformed routine")

        return routineCopy

    async def do(
            self, 
            params: dict[str, str]|None = None, fmt: str = formatHTML, 
            extraction: str|dict[str, JsonType] = "", 
            maxCacheAge: int = 0, debug: bool = False, browser: Optional["BrowserInfo"] = None, sessionID: str|None = None
        ) -> tuple[str, str, str, bool, str]:

        """
        Returns a single page or multiple pages ( via pagination )
        If pagination != None and pagination.maxPages > 1 returns multiple pages 
        isMultiPage informs if result is a single page or multiple pages

        extraction overwrites routine extraction

        When requesting data of multiple pages in
            - html format: all pages will be represented in one big html document, see createHtmlPagesViewer
            - md format  : all pages will be joined with a long line of --------- in between
            - json format: it will be "fused", see fuseData
        """
        if params is None: params = {}
        else: params = params.copy()

        data: str = ""
        contentType: str = ""
        finalUrl: str = ""
        isMultiPage: bool = False
        if sessionID == None: sessionID = uuid.uuid4().hex

        if fmt not in supportedFormats: raise APIException(f"Invalid output format '{fmt}'")

        ###### PARAMETER PARSING #######

        for key in params.keys():
            if key not in self.paramsMap:
                raise APIException(f"Unknown parameter '{key}' for routine '{self.shortHelpMessage()}'")

        for k in self.paramsMap.keys():
            if k in params:
                kind = self.paramsMap[k].kind
                if not kindMap[kind](params[k]):
                    raise APIException(f"Invalid parameter '{k}' must be of kind '{kind}'")
            else:
                if self.paramsMap[k].default == "":
                    raise APIException(f"Missing parameter '{k}' for routine '{self.shortHelpMessage()}'")
                else:
                    params[k] = self.paramsMap[k].default

        # forking and monkey patching routine
        routineCopy = self.patch(params) 

        ######### CRAWLING #############

        htmlStrs, finalUrls, _ = await getMulti(
            url=routineCopy.url, render=routineCopy.render, 
            actions=routineCopy.actions, debug=debug, maxCacheAge=maxCacheAge, 
            pagination=routineCopy.pagination, browser=browser, sessionID=sessionID
        )
        if len(htmlStrs) == 0:
            raise APIException("No pages returned")

        isMultiPage = routineCopy.pagination is not None and routineCopy.pagination.maxPages > 1

        htmlStr = htmlStrs[-1]
        finalUrl = finalUrls[-1]

        if fmt == formatHTML:
            contentType = "text/html; charset=utf-8"

            if not isMultiPage:
                data = htmlStr
            else:
                data = createHtmlPagesViewer(htmlStrs)
        elif fmt == formatMD:
            contentType = "text/markdown; charset=utf-8"

            if not isMultiPage:
                data = htmlToMarkdown(htmlStr)
            else:
                data = ""
                for s in htmlStrs:
                    data += htmlToMarkdown(s) + "\n------------------------------------------------------------\n"
        elif fmt == formatJSON:
            contentType = "application/json; charset=utf-8"

            if not finalUrl: raise ValueError(f"Internal error, finalUrl is missing for url '{self.url}'")

            # if extraction is specified routine extraction gets overwritten
            if extraction == "": extraction = self.extraction

            if extraction:
                if isinstance(extraction, dict):
                    extractionData = json.dumps(extraction)
                else:
                    _, extractionData, exists = getExtraction(name=extraction, filename="xpathschema.json")
                    if not exists:
                        raise APIException(f"Unknown extraction '{extraction}'")
            else:
                extractionName = generateUrlName(finalUrl)
                _, extractionData, exists = getExtraction(name="", filename="xpathschema.json", urlName=extractionName)
                if not exists:
                    raise APIException(f"page '{finalUrl}' currently does not have an extraction to support JSON, add new page category")

            if not isMultiPage:
                structuredData, err = parseHtml(htmlStr, extractionData)
                if err: raise err
                structuredData = removeEmptyFields(structuredData)
                data = json.dumps(structuredData, ensure_ascii=False)
            else:
                dataArr = []
                for s in htmlStrs:
                    structuredData, err = parseHtml(s, extractionData)
                    if err: raise err
                    structuredData = removeEmptyFields(structuredData)
                    dataArr.append(structuredData)
                fusedData, _ = fuseData(dataArr)
                data = json.dumps(fusedData, ensure_ascii=False)
        else:
            raise APIException(f"Unsupported format '{fmt}'")

        return data, contentType, finalUrl, isMultiPage, sessionID

def createExtractionTable() -> None:
    ''' is idempotent '''
    with sqlite3.connect(dbPath) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                domain TEXT NOT NULL,
                url TEXT NOT NULL,
                keyCount INTEGER NOT NULL,
                keyCoverage REAL NOT NULL,
                coverageScore REAL NOT NULL,
                urlName TEXT NOT NULL,
                createdAt INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """);
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idxExtractionDomain
        ON extractions(domain);
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idxExtractionUrlName
        ON extractions(urlName);
        """)
createExtractionTable()

extractionWriteLock = threading.Lock()

def getExtractionPath(id: str) -> str:
    idStart = id[:2]
    idTail = id[2:]
    return os.path.join(storageDirPath, idStart, idTail)

def addExtraction(extractionMeta: ExtractionMeta, filename: str, fileData: str = "", overwrite: bool = False) -> None:
    """#NOTE not fully atomic leaves orphans """
    with extractionWriteLock:
        if not overwrite:
            _, _, success = getExtraction(extractionMeta.name)
            if success: 
                raise HTTPException(status_code=400, detail=f"Extraction '{extractionMeta.name}' already exists, add 'overwrite=true' as query param")

        idStart = extractionMeta.id[:2]
        idTail = extractionMeta.id[2:]

        # creating fan-out directory
        # no need for fan-out be part of atomic behaviour
        folderPath = Path(os.path.join(storageDirPath, idStart))
        folderPath.mkdir(parents=False, exist_ok=True)

        folder2Path = folderPath.joinpath(idTail)
        if folder2Path.exists():
            tmpFilepath = os.path.join(storageDirPath, f"{extractionMeta.id}_{uuid.uuid4().hex}.tmp")
            filepath = folder2Path.joinpath(filename)

            with open(tmpFilepath, "w") as f:
                f.write(fileData)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmpFilepath, filepath)
        else:
            tmpFolderPath = Path(os.path.join(storageDirPath, f"{extractionMeta.id}_{uuid.uuid4().hex}.tmp"))
            tmpFolderPath.mkdir(parents=False, exist_ok=True)

            with open(tmpFolderPath.joinpath(filename), "w") as f:
                f.write(fileData)
                f.flush()
                os.fsync(f.fileno())

            os.replace(str(tmpFolderPath), str(folder2Path))

        with sqlite3.connect(dbPath) as conn:
            conn.execute(
            """
            INSERT INTO extractions
                (id, name, description, domain, url, keyCount, keyCoverage, coverageScore, urlName)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                domain = excluded.domain,
                url = excluded.url,
                keyCount = excluded.keyCount,
                keyCoverage = excluded.keyCoverage,
                coverageScore = excluded.coverageScore,
                urlName = excluded.urlName
            """,
                (extractionMeta.id, extractionMeta.name, extractionMeta.description,
                 extractionMeta.domain, extractionMeta.url, 
                 extractionMeta.keyCount, extractionMeta.keyCoverage, extractionMeta.coverageScore, extractionMeta.urlName)
            )
            conn.commit()

def deleteExtraction(name: str) -> None:
    extractionMeta, _, success = getExtraction(name)
    if not success: 
        raise APIException(f"Extraction '{name}' does not exist or could not be fetched")

    assert isinstance(extractionMeta, ExtractionMeta)

    with extractionWriteLock:
        idStart = extractionMeta.id[:2]
        idTail = extractionMeta.id[2:]
        folderPath = Path(os.path.join(storageDirPath, idStart, idTail))

        # delete extraction folder
        if folderPath.exists(): shutil.rmtree(str(folderPath))

        # delete extraction db entry
        with sqlite3.connect(dbPath) as conn:
            conn.execute("DELETE FROM extractions WHERE id = ?", (extractionMeta.id,))

def addExtractionFile(extractionID: str, filename: str, data: str) -> bool:
    """ adds a file atomicly to an existing extraction """
    with extractionWriteLock:
        idStart = extractionID[:2]
        idTail = extractionID[2:]

        folderPath = Path(os.path.join(storageDirPath, idStart, idTail))
        if not folderPath.exists(): return False

        filepath = str(folderPath.joinpath(filename))
        if Path(filepath).exists(): return False

        writeFileAtomic(filepath, data)
    return True

def editExtractionStats(extractionID: str, keyCount: int, keyCoverage: float, coverageScore: float) -> None:
    with sqlite3.connect(dbPath) as conn:
        conn.execute(
            """
            UPDATE extractions
            SET keyCount = ?, keyCoverage = ?, coverageScore = ?
            WHERE id = ?
            """,
            (keyCount, keyCoverage, coverageScore, extractionID),
        )

def moveExtractionFile(extractionID: str, oldName: str, newName: str) -> bool:
    with extractionWriteLock:
        idStart = extractionID[:2]
        idTail = extractionID[2:]

        folderPath = Path(os.path.join(storageDirPath, idStart, idTail))
        if not folderPath.exists(): return False

        oldPath = folderPath.joinpath(oldName)
        if not oldPath.exists(): return False

        newPath = folderPath.joinpath(newName)

        os.replace(oldPath, newPath)
        return True

def searchExtractions(term: str = "", domain: str = "") -> list[ExtractionMeta]:
    with sqlite3.connect(dbPath) as conn:
        conn.row_factory = sqlite3.Row
        if domain:
            rows = conn.execute("SELECT * FROM extractions WHERE domain=? AND name LIKE ?", (domain,"%"+term+"%")).fetchall()
        else:
            rows = conn.execute("SELECT * FROM extractions WHERE name LIKE ?", ("%"+term+"%",)).fetchall()
        rawResults = [dict(r) for r in rows]
        results = [
            ExtractionMeta(
                name=r["name"], 
                description=r["description"], 
                domain=r["domain"], 
                url=r["url"],
                keyCount=r["keyCount"],
                keyCoverage=r["keyCoverage"],
                coverageScore=r["coverageScore"],
            )
            for r in rawResults
        ]

    return results

def getExtraction(name: str, filename: str="", urlName: str="") -> tuple[ExtractionMeta | None, str, bool]:
    with sqlite3.connect(dbPath) as conn:
        conn.row_factory = sqlite3.Row
        if urlName:
            row = conn.execute("SELECT * from extractions where urlName=?", (urlName,)).fetchone()
        else:
            row = conn.execute("SELECT * from extractions where name=?", (name,)).fetchone()
        result = dict(row) if row else None

    if result is None: return None, "", False 

    extractionMeta = ExtractionMeta(
        name=result["name"], 
        description=result["description"], 
        domain=result["domain"], 
        url=result["url"],
        keyCount=result["keyCount"],
        keyCoverage=result["keyCoverage"],
        coverageScore=result["coverageScore"],
    )
    if filename == "": 
        # return meta only
        return extractionMeta, "", True

    idStart = result["id"][:2]
    idTail = result["id"][2:]

    extractionPath = Path(os.path.join(storageDirPath, idStart, idTail, filename))
    if not extractionPath.exists(): return None, "", False

    try:
        with open(extractionPath) as f:
            fileData = f.read()
    except FileNotFoundError:
        return None, "", False

    return extractionMeta, fileData, True

def createRoutineTable() -> None:
    ''' is idempotent '''
    with sqlite3.connect(dbPath) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS routines (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                createdAt INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """);

createRoutineTable()

routineWriteLock = threading.Lock()

def addRoutine(routine: Routine, overwrite: bool = False) -> None:
    """
    For atomic behaviour it creates file first then db entry,
    simple design but this could create orphan files, possibly implement cleanupRoutines()
    """
    with routineWriteLock:
        if not overwrite:
            _, success = getRoutine(routine.name)
            if success: 
                raise HTTPException(status_code=400, detail=f"Routine '{routine.name}' already exists, add 'overwrite=true' as query param")

        if not routine.name:
            raise APIException("Cannot add routine without a routine.name")
        rawRoutine = json.dumps(serialize(routine), indent=4, ensure_ascii=False) 

        idStart = routine.id[:2]
        idTail = routine.id[2:]

        # creating fan-out directory
        # no need for fan-out be part of atomic behaviour
        folderPath = Path(os.path.join(storageDirPath, idStart))
        folderPath.mkdir(parents=False, exist_ok=True)

        folder2Path = folderPath.joinpath(idTail)
        if folder2Path.exists():
            tmpFilepath = os.path.join(storageDirPath, f"{routine.id}_{uuid.uuid4().hex}.tmp")
            filepath = folder2Path.joinpath(f"000.json")

            with open(tmpFilepath, "w") as f:
                f.write(rawRoutine)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmpFilepath, filepath)
        else:
            tmpFolderPath = Path(os.path.join(storageDirPath, f"{routine.id}_{uuid.uuid4().hex}.tmp"))
            tmpFolderPath.mkdir(parents=False, exist_ok=True)

            with open(tmpFolderPath.joinpath(f"000.json"), "w") as f:
                f.write(rawRoutine)
                f.flush()
                os.fsync(f.fileno())

            os.replace(str(tmpFolderPath), str(folder2Path))

        with sqlite3.connect(dbPath) as conn:
            conn.execute(
                """
                INSERT INTO routines (id, name, description)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description
                """,
                (routine.id, routine.name, routine.description)
            )
            conn.commit()

def deleteRoutine(name: str) -> None:
    with routineWriteLock:
        routine, success = getRoutine(name)
        if not success: 
            raise APIException(f"Routine '{name}' does not exist or could not be fetched")

        assert isinstance(routine, Routine)

        idStart = routine.id[:2]
        idTail = routine.id[2:]
        folderPath = Path(os.path.join(storageDirPath, idStart, idTail))

        # delete extraction folder
        if folderPath.exists(): shutil.rmtree(str(folderPath))

        # delete extraction db entry
        with sqlite3.connect(dbPath) as conn:
            conn.execute("DELETE FROM routines WHERE id = ?", (routine.id,))

def getRoutine(name: str, version: int = -1) -> tuple[Routine | None, bool]:
    """
    if version == -1: get highest version nr
    """
    with sqlite3.connect(dbPath) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id from routines where name=?", (name,)).fetchone()
        result = dict(row) if row else None

    if result is None: return None, False 

    idStart = result["id"][:2]
    idTail = result["id"][2:]

    routinePath = Path(os.path.join(storageDirPath, idStart, idTail))
    if not routinePath.exists(): return None, False

    if version == -1:
        routineFilepath = max(routinePath.iterdir(), key=lambda p: p.name)
    else:
        routineFilepath = routinePath.joinpath(f"{str(version).zfill(3)}.json")

    try:
        with open(routineFilepath) as f:
            rawRoutine = f.read()
    except FileNotFoundError:
        return None, False

    return deserialize(Routine, json.loads(rawRoutine)), True

def searchRoutines(term: str) -> list[dict[str, Any]]:
    with sqlite3.connect(dbPath) as conn:
        conn.row_factory = sqlite3.Row
        if term:
            rows = conn.execute(
                "SELECT name, description FROM routines WHERE name LIKE '%' || ? || '%' OR description LIKE '%' || ? || '%' LIMIT 100",
                (term,term,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT name, description FROM routines LIMIT 100").fetchall()
        return [dict(row) for row in rows]

reXPathAxis = r"\.?\/?\/"

reXPathTagName = r"[A-Za-z_][A-Za-z0-9_.:-]*"
reXPathTag = rf"(?:\*|{reXPathTagName})"

reXPathPredicateLHS = r"(?:normalize-space\(\)|@[a-zA-Z]+)"

reXPathLiteral = r"""(?:'[^']*'|"[^"]*")"""
reXPathConcatLiteral = r"concat\(\s*" + reXPathLiteral + r"(?:\s*,\s*" + reXPathLiteral + r")+\s*\)"
reXPathFlexibleLiteral = r"(?:" + reXPathLiteral + r"|" + reXPathConcatLiteral + r")"

reXPathSinglePath = r"(?:" + reXPathAxis + reXPathTag + r"(?:\[" + reXPathPredicateLHS + r"\s*=\s*" + reXPathFlexibleLiteral + r"\])?)"
reXPath = reXPathSinglePath + r"+"

reXPathAllowedForConversion = r"(?:" + reXPathAxis + reXPathTag + r"(?:\[" + reXPathPredicateLHS + r"\s*=\s*" + reXPathLiteral + r"\])?)"

def dirtyXPathToCSS(xpath: str) -> str:
    """
    Converts easy xpath expressions to css
    Very incomplete and buggy
    """
    css = xpath.strip()

    # Remove leading //
    css = re.sub(r"^//", "", css)

    # Remove leading /
    css = re.sub(r"^/", "", css)

    # Convert / to >
    css = css.replace("/", " > ")

    # [@id='main'] or [@id="main"] -> #main
    css = re.sub(r"\[@id=['\"]([^'\"]+)['\"]\]", r"#\1", css)

    # [@class='btn'] or [@class="btn"] -> .btn
    css = re.sub(r"\[@class=['\"]([^'\"]+)['\"]\]", r".\1", css)

    # [@attr='value'] -> [attr="value"]
    css = re.sub(
        r"\[@([^=\]]+)=['\"]([^'\"]+)['\"]\]",
        r'[\1="\2"]',
        css
    )

    # [2] -> :nth-of-type(2)
    css = re.sub(r"\[(\d+)\]", r":nth-of-type(\1)", css)

    return css

def dirtyXPathTextTarget(xpath: str) -> tuple[str|None,str|None]:
    m = re.fullmatch(r"//([a-zA-Z][\w-]*)\[normalize-space\(\)=(['\"])(.*?)\2\]", xpath)
    if not m: return None, None
    else: return m.group(1), m.group(3)

def normalizeSpace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

async def deepFindElements(tab: Tab, xpath: str) -> list[WebElement]:
    """
    Lazy searches shadow roots if no results match

    If matches found in a shadow root it stops searching other shadow roots
    This may be unexpected behaviour but may improve performance
    Performance may be fast and not an issue though, we should test
    
    #TODO shadow root search is very brittle ( dirty functions ) possible implement full xpath parser 
    """
    res = await tab.find(xpath=xpath, find_all=True)
    if res: return res

    logging.debug(f"Searching for elements with selector '{xpath}' in shadow roots")
    if not re.fullmatch(reXPath, xpath):
        logging.warning(f"Unsupported xpath for shadow root search '{xpath}'")
        return []

    # this only searches same-origin iframes specify deep=True for all iframes
    shadowRoots = await tab.find_shadow_roots() 

    if "normalize-space()" not in xpath:
        cssSelector = dirtyXPathToCSS(xpath)

        for shadowRoot in shadowRoots:
            res = await shadowRoot.query(cssSelector, find_all=True)
            if res: return res
    else:
        tag, text = dirtyXPathTextTarget(xpath)
        if not re.fullmatch(reXPathAllowedForConversion, xpath) or not tag or not text:
            logging.warning(f"Unsupported xpath for shadow root search '{xpath}', try an easier one")
            return []

        for root in shadowRoots:
            candidates = await root.query(tag, find_all=True)
            matches = []

            for el in candidates:
                if normalizeSpace(await el.text) == text:
                    matches.append(el)
            if matches:
                return matches
    return []

async def ActionLoop(browser: "BrowserManager", actions: list[Action], startTime: int, tempDir: str, debugDir: str, debug: bool = True) -> None:
    tmp = None
    debugMsg = ""
    try:
        await browser.takeScreenshot(tempDir, "Page before actions", startTime)

        for i, action in enumerate(actions):
            iS = str(i+1).zfill(3)

            if action.typ == actionGoTo:
                debugMsg = f"{iS} Visit {action.v0}"
                logger.debug(debugMsg)
                await cloudflarePass(browser, action.v0, startTime=startTime, tempDir=tempDir, debugDir=debugDir, debug=debug)
            elif action.typ == actionSelect:
                debugMsg = f"{iS} Select {action.v0}"
                logger.debug(debugMsg)
                tmp = await deepFindElements(browser.page, xpath=action.v0)
                if not tmp:
                    raise ScrapingException(f"No elements found with selector '{action.v0}'")
            elif action.typ == actionWaitForAndSelect:
                debugMsg = f"{iS} Wait for '{action.v0}' for {action.v1}s"
                logger.debug(debugMsg)
                maxSeconds = int(action.v1)
                checkInterval=0.1

                waitStartTime = time.monotonic()
                while int(time.monotonic() - waitStartTime) <= maxSeconds:
                    tmp = await deepFindElements(browser.page, xpath=action.v0)
                    if tmp: break
                    await asyncio.sleep(checkInterval)

                if not tmp:
                    raise ScrapingException(f"No elements found with selector '{action.v0}' in {maxSeconds} seconds")

            elif action.typ == actionClick: 
                debugMsg = f"{iS} Click element"
                logger.debug(debugMsg)
                if not tmp:
                    raise ScrapingException("No elements selected")
                if len(tmp) > 1:
                    raise ScrapingException(f"Selection ambigous, {len(tmp)} elements selected")
                else:
                    await tmp[0].click(humanize=browser.humanize)
            elif action.typ == actionType:
                debugMsg = f"{iS} Type into element"
                logger.debug(debugMsg)
                if not tmp:
                    raise ScrapingException("No elements selected")
                if len(tmp) > 1:
                    raise ScrapingException(f"Selection ambigous, {len(tmp)} elements selected")
                else:
                    await tmp[0].type_text(action.v0, humanize=browser.humanize)
            elif action.typ == actionKeyboardEnter:
                debugMsg = f"{iS} Type Enter on keyboard"
                logger.debug(debugMsg)
                # keyboard.press(Key.ENTER) not working reliably so we call this instead
                await pydollKeyboardEnter(browser)
            elif action.typ == actionSleep:
                debugMsg = f"{iS} Sleep {action.v0}s"
                logger.debug(debugMsg)
                await asyncio.sleep(int(action.v0))
            elif action.typ == actionFilterText:
                debugMsg = f"{iS} Filter selection by text: {action.v0}"
                logger.debug(debugMsg)
                if not tmp:
                    raise ScrapingException("No elements selected")

                elements = tmp
                tmp = []
                for element in elements:
                    text = await element.text
                    if action.v0 in text:
                        tmp.append(element)
            elif action.typ == actionFilterAttribute:
                debugMsg = f"{iS} Filter selection by attribute {action.v0}={action.v1}"
                logger.debug(debugMsg)
                if not tmp:
                    raise ScrapingException("No elements selected")

                elements = tmp
                tmp = []
                for element in elements:
                    text = element.get_attribute(action.v0) or ""
                    if action.v1 in text:
                        tmp.append(element)
            elif action.typ == actionFilterIndex:
                debugMsg = f"{iS} Filter selection by index {action.v0}"
                logger.debug(debugMsg)
                if not tmp:
                    raise ScrapingException("No elements selected")

                tmp = [tmp[int(action.v0)]]
            elif action.typ == actionExecuteScript:
                debugMsg = f"{iS} Execute javascript"
                logger.debug(debugMsg)
                await browser.page.execute_script(action.v0)
            else:
                raise APIException(f"Invalid action '{action.typ}'")

            if debug: await browser.takeScreenshot(tempDir, debugMsg, startTime)
    except APIException as e:
        raise e
    except Exception as e:
        errorMsg = f"{debugMsg}: {str(e)}"
        if debug: await browser.takeScreenshot(tempDir, errorMsg, startTime, isError=True)

        raise ScrapingException(errorMsg)
    finally:
        if debug:
            createPdfFromFolder(tempDir, os.path.join(debugDir, f"{int(time.time() * 1000)}_browser.pdf"))
        shutil.rmtree(tempDir)

class BrowserInfo:
    def __init__(self, id: str, publicAddress: str, privateAddress: str, browserNr: str):
        self.id = id
        self.publicAddress = publicAddress
        self.privateAddress = privateAddress
        self.browserNr = browserNr

browserOSX = "osx"
browserLinuxXVFB = "linux_xvfb"

class BrowserManager:
    userDataDir: str
    maxCount: int
    gotoCount: int
    typ: str
    virtualFrameBufferProcess: subprocess.Popen[Any]|None
    displayNumber: str
    contextID: str
    page: Tab
    isOpen: bool
    isClone: bool
    humanize: bool
    proxy: str

    def __init__(self, typ: str = browserLinuxXVFB, humanize: bool = True, proxy: str = "") -> None:
        profile = str(uuid.uuid4())
        self.userDataDir = f"/tmp/chrome_{profile}"
        
        logger.info(f"Created profile {profile}")
        
        self.maxCount = 10 # after how many requests to delete all cookies  
        self.gotoCount = 0
        self.typ = typ
        self.virtualFrameBufferProcess = None
        self.displayNumber = ""
        self.contextID = ""
        self.isOpen = False
        self.isClone = False
        self.humanize = humanize
        self.proxy = proxy

    async def clearContext(self) -> None: 
        params = {"origin": "*", "storageTypes": "all"}
        await self.page._execute_command(
            Command(method="Storage.clearDataForOrigin", params=params)
        )
        # this immediately detects when browser freezes, e.g. after computer sleeps
        # so it can be closed and reopened
        await self.page.go_to("about:blank", timeout=1) 

    def hideWindow(self) -> None:
        if not self.browser._browser_process_manager._process:
            raise APIException("Browser process not started")

        if self.typ == browserOSX:
            subprocess.run([
                "osascript", "-e",
                f'''
                tell application "System Events"
                    tell (first process whose unix id is {self.browser._browser_process_manager._process.pid})
                        repeat with w in every window
                            set position of w to {{25000, 25000}}
                        end repeat
                    end tell
                end tell
                '''
            ])

    async def takeScreenshot(self, dirPath: str, debugMsg: str, startTime: int, isError: bool = False) -> None:
        '''
        startTime is the time the task was started and used for debug messages 
        isError = True adds a red border to the image
        '''
        timestampMs = int(time.time() * 1000)
        secondsPast = (timestampMs // 1000) - startTime
        # for correct ordering we put timestamp in ms into filepath
        # collisions with other images unlikely because we use ms and actions
        # should take longer than that normally
        screenshotPath = f'{dirPath}/{timestampMs}_screenshot.jpeg'
        debugMsg = f"{str(secondsPast).zfill(2)}s {debugMsg}" 

        await self.page.take_screenshot(screenshotPath, quality=100)
        if isError: addRedBorder(screenshotPath)
        addCaption(screenshotPath, debugMsg)

    async def cloneBrowser(self) -> "BrowserManager":
        contextID = await self.browser.create_browser_context()
        page = await self.browser.new_tab('', browser_context_id=contextID)
        newBrowser = BrowserManager()
        newBrowser.isClone = True
        newBrowser.page = page
        newBrowser.browser = self.browser
        newBrowser.contextID = contextID
        newBrowser.isOpen = self.isOpen
        newBrowser.displayNumber = self.displayNumber
        newBrowser.humanize = self.humanize
        newBrowser.proxy = self.proxy
        return newBrowser

    async def open(self) -> None:
        self.gotoCount = 0
        if not self.isClone and not self.isOpen:
            displayNumberStr = ""
            if self.typ == browserLinuxXVFB:
                self.virtualFrameBufferProcess = subprocess.Popen(
                    # -displayfd 1 sends a line to stdout (= fd 1) with auto assigned display number when ready
                    # Plenty of numbers: theoretical min max display number: 0 to 2**31 - 1 ( 2 billion )
                    ["Xvfb", "-displayfd", "1", "-screen", "0", "1920x1080x24"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                #TODO This waits forever may not be optimal
                assert self.virtualFrameBufferProcess.stdout != None
                self.displayNumber = self.virtualFrameBufferProcess.stdout.readline().strip()
                if not self.displayNumber:
                    raise Exception("Could not start Xvfb, unable to assign displayNumber")

                logger.info(f"Acquired Xvfb display number {self.displayNumber}")
                displayNumberStr = f":{self.displayNumber}"

            self.browser = getChrome(displayNumberStr, self.userDataDir, proxy=self.proxy)
            self.page = await self.browser.start()

            await fixWebRTCLeak(self.page)
            await blockMedia(self.page)

            self.isOpen = True
            self.hideWindow() 

    async def close(self) -> None: 
        if not self.isClone and self.isOpen:
            try:
                await self.browser.stop()
            except: 
                pass
            shutil.rmtree(self.userDataDir) 

            self.displayNumber = ""
            if self.typ == browserLinuxXVFB and self.virtualFrameBufferProcess != None:

                self.virtualFrameBufferProcess.terminate()

                try:
                    self.virtualFrameBufferProcess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.virtualFrameBufferProcess.kill()
        
            self.isOpen = False

    async def go_to(self, url: str, timeout: int = 40) -> None:
        self.gotoCount += 1
        logger.info(f"browser goto count {self.gotoCount}")
        await self.page.go_to(url, timeout=timeout)

async def blockMedia(tab: Tab) -> None:
    ''' for faster loading '''
    async def blockMediaRequests(tab: Tab, event: dict[str, Any]) -> None:
        # we send back real response to avoid infinite loading loops
        ONE_PIXEL_GIF_BASE64 = "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
        requestId = event['params']['requestId']
        resourceType = event['params']['resourceType']
        if resourceType in (ResourceType.IMAGE, ResourceType.MEDIA, ResourceType.FONT):
            await tab.fulfill_request(
                request_id=requestId,
                response_code=200,
                response_headers=[{"name": "Content-Type","value": "image/gif"}],
                body=ONE_PIXEL_GIF_BASE64,
            )
        else:
            await tab.continue_request(requestId)
    
    # By specifying url patterns we only intercept requests matching those patterns
    # We dont use pydolls Fetch.enable since it only lets us specify 1 url pattern
    rawPatterns = [
        # Images
        "*.png","*.jpg","*.jpeg","*.gif","*.webp","*.avif","*.bmp","*.tif","*.tiff",

        # Video
        "*.mp4","*.webm","*.mov","*.m4v","*.avi","*.mkv",

        # Audio (if you also want to block it)
        "*.mp3","*.wav","*.ogg","*.m4a","*.aac","*.flac",

        # Fonts
        "*.woff","*.woff2","*.ttf","*.otf","*.eot",
    ]
    patterns = [{"urlPattern": p,"requestStage": "Request"} for p in rawPatterns]
    params = {"patterns": patterns}

    await tab._execute_command(Command(method="Fetch.enable", params=params))
    await tab.on(FetchEvent.REQUEST_PAUSED, partial(blockMediaRequests, tab))
    

async def fixWebRTCLeak(tab: Tab) -> None:
    '''Needs to be called on every new tab'''
    #TODO currenlty removes RTC entirely not returning IP Address, which deviates from standard browsers
    script = """
    if (window.RTCPeerConnection) {
            const originalRTCPeerConnection = window.RTCPeerConnection;
            window.RTCPeerConnection = function(config) {
                if (config && config.iceServers) {
                    config.iceServers = []; // Remove all iceServers to prevent IP leakage
                }
                return new originalRTCPeerConnection(config);
            };
            window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
        }

        window.RTCSessionDescription = undefined;
        window.RTCIceCandidate = undefined;
    """
    params = {"source": script}

    # NOTE disable_page_events clears all added scripts via Page.* and they must be added again
    await tab.enable_page_events()
    await tab._execute_command(
        Command(method="Page.addScriptToEvaluateOnNewDocument", params=params)
    )

def createCache() -> None:
    ''' is idempotent '''
    with sqlite3.connect(cacheDBPath) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT NOT NULL PRIMARY KEY,
                createdAt INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                finalUrl TEXT,
                contentType TEXT,
                isEmpty INTEGER NOT NULL DEFAULT 0
            )
        """);
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idxCacheCreatedAt
            ON cache(createdAt);
        """)

        conn.commit()

createCache()

def setCache(signatureStr: str, response: str, finalUrl: str, contentType: str) -> None:
    """
    One never practically encounters a collision on random data on sha1 in a lifetime
    Even if one does this is just a cache, not critical data

    Atomic: Worst case, file may be newer but db still indicating older age

    if response is "" it creates a virtual db entry without a file and sets isEmpty=1
    this can be useful for aggregate entries e.g. see pagination
    """
    key = sha1(signatureStr)
    isEmpty = 1 if response == "" else 0
    with sqlite3.connect(cacheDBPath) as conn:
        conn.execute("""
            INSERT INTO cache ("key", finalUrl, contentType, isEmpty) VALUES (?, ?, ?, ?)
            ON CONFLICT("key") DO UPDATE SET
                createdAt = strftime('%s', 'now'),
                finalUrl = excluded.finalUrl,
                contentType = excluded.contentType,
                isEmpty = excluded.isEmpty
        """, (key, finalUrl, contentType, isEmpty))
        if not isEmpty:
            idStart = key[:2]
            idTail = key[2:]

            Path(os.path.join(cacheDirPath, f"{idStart}")).mkdir(parents=False, exist_ok=True)

            tmpFilepath = os.path.join(cacheDirPath, f"{idStart}/{idTail}_{uuid.uuid4().hex}.html.tmp")
            filepath = os.path.join(cacheDirPath, f"{idStart}/{idTail}.html")

            with open(tmpFilepath, "w") as f:
                f.write(response)

            os.replace(tmpFilepath, filepath)
        conn.commit()

def getCache(signatureStr: str, maxAgeSeconds: int = 0) -> tuple[bool, str, str, str]:
    """
    Returns cachedFound, data, finalUrl 
    """
    key = sha1(signatureStr)
    result = None
    with sqlite3.connect(cacheDBPath) as conn:
        conn.row_factory = sqlite3.Row

        minCreatedAt = int(time.time()) - maxAgeSeconds
        row = conn.execute('SELECT * FROM cache WHERE "key"=? AND createdAt>=?', (key,minCreatedAt)).fetchone()

        result = dict(row) if row else None

    if result is None:
        return False, "", "", ""
        
    if result["isEmpty"] == 1:
        return True, "", result["finalUrl"], result["contentType"]
    idStart = key[:2]
    idTail = key[2:]
    filePath = Path(os.path.join(cacheDirPath, f"{idStart}/{idTail}.html"))
    if filePath.is_file():
        with open(str(filePath)) as f:
            return True, f.read(), result["finalUrl"], result["contentType"]
    else:
        return False, "", "", ""


async def screenshotLoop(browser: BrowserManager, dirPath: str, debugMsg: str, startTime: int) -> None:
    try:
        while True:
            await asyncio.sleep(3)
            await browser.takeScreenshot(dirPath, debugMsg, startTime) 
    except asyncio.CancelledError:
        pass

async def cloudflarePass(browser: BrowserManager, url: str, startTime: int, tempDir: str, debugDir: str, debug: bool = False) -> bool:
    hasCloudflare = False

    screenshotTask = None

    if debug:
        screenshotTask = asyncio.create_task(
            screenshotLoop(browser, dirPath=tempDir, debugMsg=f"Goto {url}", startTime=startTime)
        )

    try:
        async with browser.page.expect_and_bypass_cloudflare_captcha():
            await browser.go_to(url)

            # just internal testing maybe remove until "has cloudflare" print
            htmlSrc = await browser.page.page_source
            tree = html.fromstring(htmlSrc)
            scripts: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//script"))
            for script in scripts:
                src = script.get("src", "")
                if "challenges.cloudflare.com" in src:
                    hasCloudflare = True
                    break

            logger.debug(f"has cloudflare {hasCloudflare}")
            logger.debug('Page loaded, waiting for captcha to be handled...')
    finally:
        if screenshotTask is not None:
            screenshotTask.cancel()
            await asyncio.gather(screenshotTask, return_exceptions=True)

    if hasCloudflare and debug:
        await browser.takeScreenshot(tempDir, "Passed cloudflare", startTime)

    return hasCloudflare

async def pydollKeyboardEnter(browser: BrowserManager) -> None:
    """ see: https://github.com/ChromeDevTools/devtools-protocol/issues/45 """
    #TODO Possibly implement directly in pydoll
    command_down = InputCommands.dispatch_key_event(
        type=KeyEventType.RAW_KEY_DOWN,
        windows_virtual_key_code=13,
        unmodified_text="\r",
        text="\r",
    )
    await browser.page.keyboard._executor._execute_command(command_down)
    command_char = InputCommands.dispatch_key_event(
        type=KeyEventType.CHAR,
        windows_virtual_key_code=13,
        unmodified_text="\r",
        text="\r",
    )
    await browser.page.keyboard._executor._execute_command(command_char)
    command_up = InputCommands.dispatch_key_event(
        type=KeyEventType.KEY_UP,
        windows_virtual_key_code=13,
        unmodified_text="\r",
        text="\r",
    )
    await browser.page.keyboard._executor._execute_command(command_up)

def resolveRelativeUrls(htmlStr: str, baseUrl: str) -> str:
    lxmlRoot = html.fromstring(htmlStr)
    assert isinstance(lxmlRoot, html.HtmlElement)
    lxmlRoot.make_links_absolute(baseUrl)

    response = html.tostring(lxmlRoot, encoding="unicode")
    assert isinstance(response, str)
    return response

async def getMulti(url: str, render: bool = False, actions: list[Action] = [], debug: bool=False, maxCacheAge: int = 0, pagination: Pagination | None = None, browser: BrowserInfo|None = None, sessionID: str = "defaultSession") -> tuple[list[str], list[str], list[str]]:
    """ 
    Behaves similar to Get but supports pagination
    Returns array for each return value of Get
    """
    htmlStrs, finalUrls, signatureStrs = [], [], []

    multiSignatureStrRoot = url + "::::" + generateSignature(actions) + "::::" + generateSignature(render) 

    if pagination:
        # Since we assume pagination requires browser state of the previous pages, 
        # When pagination.maxPages is higher than before we need to go through rendering all previous pages again 

        cachedFound, _, _, _ = getCache(multiSignatureStrRoot + "::::" + str(pagination.maxPages), maxAgeSeconds=maxCacheAge)
        if not cachedFound: maxCacheAge = 0

    htmlStr, finalUrl, signatureStr = await get(
        url=url, render=render, actions=actions, debug=debug, 
        maxCacheAge=maxCacheAge, browser=browser, sessionID=sessionID
    )

    htmlStrs.append(htmlStr)
    finalUrls.append(finalUrl)
    signatureStrs.append(signatureStr)

    if pagination:
        # create virtual cache entry for first page
        setCache(multiSignatureStrRoot + "::::" + str(1), "", "", "")

        for i in range(pagination.maxPages-1):
            actions = []
            url = ""
            if render:
                actions = [Action(actionSelect, str(pagination.nextPageXPath), ""), Action(actionClick, "", ""), Action(actionSleep, str(pagination.clickDelaySeconds), "")] 
            else:
                selection = html.fromstring(htmlStr).xpath(pagination.nextPageXPath)
                if not selection or not isinstance(selection, list): 
                    # matches action behaviour since it will raise an error if a selector is not found in browser inside ActionLoop
                    raise ScrapingException(f"No elements found with selector '{pagination.nextPageXPath}'")
                elif not isinstance(selection[0], html.HtmlElement):
                    raise ScrapingException(f"Invalid selector {pagination.nextPageXPath}")
                url = selection[0].attrib.get("href", "")
                if url == "": break

                await asyncio.sleep(pagination.clickDelaySeconds)

            # signatureStr of previous page is to cache in combination with all previous pages urls, actions, ...

            #TODO there is a possible issue if we get for example 
            # first 4 pages then e.g. set maxCacheAge=0 and just get 2 pages 
            # overwriting the first 2 pages of the 4 page cached request
            # this may not be an issue
            htmlStr, finalUrl, signatureStr = await get(
                url=url, render=render, actions=actions, debug=debug, 
                maxCacheAge=maxCacheAge, browser=browser, sessionID=sessionID, prevSignatureStr=signatureStr
            )

            htmlStrs.append(htmlStr);
            finalUrls.append(finalUrl);
            signatureStrs.append(signatureStr)

            # virtual cache entry for every page up to maxPages
            # +1: since pagination starts at page 2, 
            # +1: 1-indexed
            setCache(multiSignatureStrRoot + "::::" + str(i+1+1), "", "", "")

    return htmlStrs, finalUrls, signatureStrs

def getUserDebugDir(sessionID: str) -> str:
    return os.path.join(debugDirPath, f"{sessionID}")

async def get(url: str, render: bool = False, actions: list[Action] = [], debug: bool=False, maxCacheAge: int = 0, browser: BrowserInfo|None = None, sessionID: str = "defaultSession", prevSignatureStr: str = "") -> tuple[str, str, str]:
    signatureStr: str = ""
    htmlSrc: str = ""
    userDebugDir: str = getUserDebugDir(sessionID)
    finalUrl: str = "" # url after all actions completed
    contentType: str = ""
    cachedFound: bool = False

    if not render and actions:
        raise APIException(f"Task actions only available if render=True")

    # if prevSignatureStr, url, actions or render change item will be recached
    signatureStr = prevSignatureStr + "::::" + url + "::::" + generateSignature(actions) + "::::" + generateSignature(render)

    if debug:
        folder_path = Path(userDebugDir)
        folder_path.mkdir(parents=False, exist_ok=True)

    cachedFound, htmlSrc, finalUrl, contentType = getCache(signatureStr, maxAgeSeconds=maxCacheAge)

    if render and not cachedFound:
        assert browser != None

        async with AsyncSession() as s:
            #TODO always assumes localhost for now, does not try publicAddress or privateAddress of BrowserInfo
            resp = await s.get(
                "localhost" + ":18765" + "/browser", 
                json={
                    "browserNr": browser.browserNr, "sessionID": sessionID, "clearContext": prevSignatureStr == "", 
                    "debug": debug, "url": url, "actions": [[a.typ, a.v0, a.v1] for a in actions]
                },
                timeout=60
            )
        if resp.status_code < 200 or resp.status_code > 299:
            if not resp.text: resp.raise_for_status()
            raise HTTPException(status_code=resp.status_code, detail=f"{json.loads(resp.text)['detail']}")
        data = json.loads(resp.text)

        htmlSrc = data["data"]
        finalUrl = data["finalUrl"]
        contentType = data["contentType"]
                
    elif not cachedFound:
        async with AsyncSession() as s:
            r = await s.get(url, impersonate="chrome")
            finalUrl = r.url
            htmlSrc = r.text
            contentType = r.headers.get("content-type", "")

    if debug:
        with open(os.path.join(userDebugDir, f"{int(time.time() * 1000)}_final_site.html"), "w") as f: f.write(htmlSrc)

    if not cachedFound:
        setCache(signatureStr, htmlSrc, finalUrl, contentType)

    if "text/html" in contentType:
        htmlSrc = resolveRelativeUrls(htmlSrc, finalUrl)
    return htmlSrc, finalUrl, signatureStr

browserStatusIdle = 'idle'
browserStatusTaken = 'taken'

def createBrowsersTable() -> None:
    with sqlite3.connect(dbPath) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS browsers (
            id TEXT NOT NULL,
            workerId TEXT NOT NULL,
            browserNr INTEGER NOT NULL,
            publicAddress TEXT NOT NULL,
            privateAddress TEXT NOT NULL,
            lastHeartbeat TEXT NOT NULL,
            browserType TEXT NOT NULL,
            status TEXT NOT NULL,

            PRIMARY KEY (id),
            UNIQUE (workerId, browserNr)
        )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_lastHeartbeat
            ON browsers (lastHeartbeat)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_browserType
            ON browsers (browserType)
        """)

createBrowsersTable()

def registerBrowser(workerId: str, browserNr: int, publicAddress: str, privateAddress: str,browserType: str) -> None:
    browserId = workerId + f"{browserNr:04x}"

    with sqlite3.connect(dbPath) as conn:
        conn.execute("""
            INSERT INTO browsers 
                ( id, workerId, browserNr, publicAddress, privateAddress, browserType, lastHeartbeat, status )
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(id) DO UPDATE SET
                publicAddress = excluded.publicAddress,
                privateAddress = excluded.privateAddress,
                browserType = excluded.browserType,
                lastHeartbeat = datetime('now')
        """, (browserId, workerId, browserNr, publicAddress, privateAddress, browserType, browserStatusIdle))

def getBrowser() -> BrowserInfo | None:
    with sqlite3.connect(dbPath) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT id, publicAddress, privateAddress, browserNr
                FROM browsers
                WHERE status = ? AND lastHeartbeat > datetime('now', '-30 seconds')
                LIMIT 1
            """, (browserStatusIdle,)).fetchone()

            if row is None: conn.rollback(); return None

            b = BrowserInfo(row[0], row[1], row[2], row[3])

            conn.execute(
                "UPDATE browsers SET status = ? WHERE id = ?", 
                (browserStatusTaken, b.id)
            )

            return b
        except: conn.rollback(); raise

def returnBrowser(browserId: str) -> None:
    with sqlite3.connect(dbPath) as conn:
        conn.execute(
            "UPDATE browsers SET status = ? WHERE id = ?", (browserStatusIdle, browserId)
        )
