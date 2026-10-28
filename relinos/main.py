import logging
import json 
import html
from urllib.parse import quote
from pathlib import Path
import uuid
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictInt, StrictFloat
from starlette.types import Scope

from relinos.config import debugDirPath, serverName

from relinos.scraping_api import Action, Pagination, ScrapingException, APIException, Routine, getRoutine, searchRoutines, searchExtractions, RoutineParam, getBrowser, returnBrowser, ExtractionMeta, addExtraction, getExtraction, searchExtractions, deleteExtraction, RoutineParam, Patch, addRoutine, kindStr, deleteRoutine
from relinos.normalize import urlToDomain, keyCounts
from relinos.parse import getCoverageScore, ParseException, JsonType
from relinos.tools import serialize

logger = logging.getLogger(__name__)


class ActionModel(BaseModel):
    typ: str
    v0: str = ""
    v1: str = ""

def parseActions(modelActions: list[ActionModel]|list[tuple[str, str, str]]) -> list[Action]:
    actions = []
    for a in modelActions:
        if isinstance(a, tuple):
            action = Action(a[0], a[1], a[2])
        elif isinstance(a, ActionModel):
            action = Action(a.typ, a.v0, a.v1)
        else:
            raise Exception(f"Could not parse actions, invalid type {type(modelActions)}")
        actions.append(action)

    return actions

def parsePagination(modelPagination: tuple[str, int]|None) -> Pagination|None:
    if modelPagination:
        pagination = Pagination(modelPagination[0], int(modelPagination[1]))
    else:
        pagination = None

    return pagination

class GetRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    render: bool = False
    actions: list[ActionModel] | list[tuple[str, str, str]] = []
    pagination: tuple[str, int] | None = None

    format: str = "html"
    extraction: str|dict[str, JsonType] = ""

    debug: bool = False
    cache: str = "0s"
    includeMeta: bool = False

class PatchModel(BaseModel):
    keypath: str
    start: int = -1
    end: int = -1
    transform: str = ""

class RoutineParamModel(BaseModel):
    name: str
    description: str = ""
    patches: list[PatchModel]
    default: str = ""
    kind: str = kindStr 

class AddRoutineRequestModel(GetRequestModel):
    description: str = ""
    overwrite: bool = False
    params: list[RoutineParamModel]

class RoutineRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # need to use Strict otherwise bool is valid
    params: dict[str, StrictInt|StrictFloat|str]

    format: str = "html"
    extraction: str|dict[str, JsonType] = ""

    debug: bool = False
    cache: str = "0s"
    includeMeta: bool = False

# When adding an extraction we actually run it to ensure its working. 
# This can be done by specifying a valid /get or a valid /do request body
class AddExtractionViaGetModel(GetRequestModel):
    description: str = ""
    overwrite: bool = False

class AddExtractionViaDoModel(RoutineRequestModel):
    description: str = ""
    overwrite: bool = False

# debug files are cached for 1 year since they practically never change once get/getMulti response returned
class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)

        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

        return response

durationRe = re.compile(r"(\d+)([smhdy])")
def durationToSeconds(duration: str) -> tuple[int, Exception|None]:
    match = durationRe.fullmatch(duration)
    if not match:
        return 0, Exception(f"Cannot convert invalid duration '{duration}' to seconds")

    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "s":
        return amount, None
    elif unit == "m":
        return amount * 60, None
    elif unit == "h":
        return amount * 60 * 60, None
    elif unit == "d": 
        return amount * 60 * 60 * 24, None
    elif unit == "y": 
        return int(amount * 60 * 60 * 24 * 365.24), None

    return 0, Exception(f"Cannot convert invalid duration '{duration}' to seconds")

app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.mount("/debug/files", CachedStaticFiles(directory=debugDirPath), name="debug")

@app.exception_handler(HTTPException)
async def customExceptionHandler(request: Request, exc: HTTPException) -> Response:
    # use FastAPI's normal behavior
    data = { "detail": exc.detail }
    headers = dict(exc.headers or {})
    if hasattr(request.state, "sessionID"):
        headers["X-Session-ID"] = request.state.sessionID
        if getattr(request.state, "userDebug", False):
            headers["X-Debug-URL"] = serverName + f"/debug/{request.state.sessionID}"

    return JSONResponse(
        status_code=exc.status_code,
        content=data,
        headers=headers,
    )

@app.exception_handler(Exception)
async def globalExceptionHandler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        httpExc = exc
    elif isinstance(exc, APIException):
        httpExc = HTTPException(status_code=400, detail=str(exc))
    elif isinstance(exc, (ScrapingException, ParseException)):
        httpExc = HTTPException(status_code=422, detail=str(exc))
    else:
        httpExc = HTTPException(status_code=500, detail="Internal Error")

    return await customExceptionHandler(request, httpExc)

# Practically guessing any uuid4 (or any random 128 bit string) is impossible 
# even with 1 billion tries per second it would take vastly longer than the age of the universe.
@app.get("/debug/{sessionID}", response_class=HTMLResponse)
async def debugSession(sessionID: str) -> HTMLResponse:
    if not sessionID.isalnum():
        raise HTTPException(status_code=400, detail="Invalid sessionID")

    sessionDir = Path(debugDirPath) / sessionID

    if not sessionDir.is_dir():
        return HTMLResponse("Not found", status_code=404)

    files = []
    for path in sorted(sessionDir.iterdir()):
        if path.is_file():
            files.append(
                f'<li><a href="/debug/files/{sessionID}/{quote(path.name)}">'
                f'{html.escape(path.name)}</a></li>'
            )

    return HTMLResponse(f"""
    <html>
        <body>
            <h1>Debug {sessionID}</h1>
            <ul>
                {''.join(files)}
            </ul>
        </body>
    </html>
    """)

@app.get("/routines")
async def search_routines(q: str = "") -> Response:
    return JSONResponse(searchRoutines(q))

@app.post("/routines/{routineName}")
async def add_routine(request: Request, routineName: str, req: AddRoutineRequestModel) -> Response:
    # parsing routine params
    routineParams = []
    for pModel in req.params:
        patches = []
        for paModel in pModel.patches:
            patches.append(
                Patch(paModel.keypath, paModel.start, paModel.end, paModel.transform)  
            )
        routineParams.append(
            RoutineParam(
                name=pModel.name, description=pModel.description, 
                patches=patches, default=pModel.default, kind=pModel.kind
            )
        )

    actions = parseActions(req.actions) 
    pagination = parsePagination(req.pagination)

    maxCacheAge, err = durationToSeconds(req.cache)
    if err: raise HTTPException(status_code=400, detail=f"Invalid cache duration '{req.cache}', valid examples '30s', '10m', '1h', '7d', '10y'")

    # MONKEY PATCH and return patched result
    routine = Routine(
        name=routineName, description=req.description, params=routineParams, 
        url=req.url, render=req.render, actions=actions, 
        pagination=pagination, extraction=req.extraction
    )

    patchedRoutine = serialize(routine.patch({k.name:k.name.upper() for k in req.params}))
    del patchedRoutine["name"]
    del patchedRoutine["description"]
    del patchedRoutine["params"]

    addRoutine(routine, overwrite=req.overwrite)
    return JSONResponse({"example": patchedRoutine})

@app.get("/routines/{routineName}", response_class=HTMLResponse)
async def routine_details(request: Request, routineName: str) -> Response:
    routine, success = getRoutine(routineName)
    if not success: raise HTTPException(status_code=404, detail=f"Unknown routine '{routineName}'")
    return JSONResponse(serialize(routine))

@app.delete("/routines/{routineName}", response_class=HTMLResponse)
async def delete_routine(request: Request, routineName: str) -> None:
    deleteRoutine(routineName)

@app.get("/do", response_class=HTMLResponse)
async def routine(request: Request, req: RoutineRequestModel) -> Response:
    request.state.sessionID = uuid.uuid4().hex
    request.state.userDebug = req.debug

    routine, success = getRoutine(req.name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Unknown routine '{req.name}'")
    assert routine != None

    maxCacheAge, err = durationToSeconds(req.cache)
    if err: raise HTTPException(status_code=400, detail=f"Invalid cache duration '{req.cache}', valid examples '30s', '10m', '1h', '7d', '10y'")

    #TODO this and on /get, gets a browser even if we have a cached version
    browserInfo = None
    if routine.render:
        browserInfo = getBrowser()
        if browserInfo == None:
            raise APIException("All browsers busy")
    try:
        data, contentType, finalUrl, isMultiPage, sessionID = await routine.do(
            params={k: str(v) for k, v in req.params.items()},
            fmt=req.format, 
            extraction=req.extraction, 
            maxCacheAge=maxCacheAge, 
            debug=req.debug, 
            browser=browserInfo,
            sessionID=request.state.sessionID
        )
    except:
        raise 
    finally:
        if browserInfo:
            returnBrowser(browserInfo.id)

    headers = { "X-Session-ID": request.state.sessionID }
    if req.debug: 
        headers["X-Debug-URL"] = serverName + f"/debug/{sessionID}"
    if req.includeMeta:
        return Response(
            json.dumps({
                "contentType": contentType, 
                "finalUrl": finalUrl, 
                "isMultiPage": isMultiPage, 
                "data": data}), 
            media_type="application/json; charset=utf-8",
            headers=headers
        )
    else:
        return Response(data, media_type=contentType, headers=headers)

@app.get("/extractions")
async def search_extractions(q: str = "", domain: str = "") -> Response:
    extractions = searchExtractions(term=q, domain=domain)
    # only displays some properties
    data = []
    for e in extractions:
        data.append({"name": e.name, "description": e.description, "domain": e.domain, "url": e.url})

    return JSONResponse(data)

@app.get("/extractions/{extractionName}", response_class=HTMLResponse)
async def extraction_details(request: Request, extractionName: str) -> Response:
    meta, xpathschema, success = getExtraction(extractionName, "xpathschema.json")

    if not success: raise HTTPException(status_code=404, detail=f"Unknown extraction '{extractionName}'")
    assert isinstance(meta, ExtractionMeta)

    return JSONResponse({
        "name": meta.name,
        "description": meta.description,
        "domain": meta.description,
        "url": meta.url,
        "keyCount": meta.keyCount,
        "keyCoverage": meta.keyCoverage,
        "coverageScore": meta.coverageScore,
        "extraction": json.loads(xpathschema)
    })

@app.post("/extractions/{extractionName}")
async def add_extraction(request: Request, extractionName: str, req: AddExtractionViaGetModel|AddExtractionViaDoModel) -> None:
    if req.extraction == "":
        raise HTTPException(status_code=422, detail=f"The 'extraction' key is missing, specify an xpathschema")
    if isinstance(req.extraction, str):
        raise HTTPException(status_code=422, detail=f"Must specify a full xpathschema inside 'extraction' not a name")

    if isinstance(req, AddExtractionViaGetModel):
        # interpret as /get
        reqData = GetRequestModel(
            url=req.url, render=req.render, actions=req.actions, pagination=req.pagination, 
            format="json", extraction=req.extraction, debug=False, cache=req.cache, includeMeta=True
        )
        response = await get(request, reqData)
    else:
        # interpret as /do
        reqData2 = RoutineRequestModel(
            name=req.name, params=req.params, format="json", extraction=req.extraction, 
            debug=False, cache=req.cache, includeMeta=True
        )
        response = await routine(request, reqData2)
    d = json.loads(bytes(response.body))

    resultData = json.loads(d["data"])
    keyCount, _, keyCoverage = keyCounts(resultData)
    coverageScore, _ = getCoverageScore(resultData)

    extractionMeta = ExtractionMeta(
        name=extractionName, description=req.description, 
        domain=urlToDomain(d["finalUrl"]), url=d["finalUrl"], 
        keyCount=keyCount, keyCoverage=keyCoverage, coverageScore=coverageScore
    )
    addExtraction(extractionMeta, filename="xpathschema.json", fileData=json.dumps(req.extraction, indent=4, ensure_ascii=False), overwrite=req.overwrite)

@app.delete("/extractions/{extractionName}", response_class=HTMLResponse)
async def delete_extraction(request: Request, extractionName: str) -> None:
    deleteExtraction(extractionName)

@app.get("/get", response_class=HTMLResponse)
async def get(request: Request, req: GetRequestModel) -> Response:
    request.state.sessionID = uuid.uuid4().hex
    request.state.userDebug = req.debug

    actions = parseActions(req.actions)
    pagination = parsePagination(req.pagination)
    
    maxCacheAge, err = durationToSeconds(req.cache)
    if err: raise HTTPException(status_code=400, detail=f"Invalid cache duration '{req.cache}', valid examples '30s', '10m', '1h', '7d', '10y'")

    routine = Routine(
        name="", description="", params=[], 
        url=req.url, render=req.render, actions=actions, pagination=pagination
    )
    browserInfo = None
    if req.render:
        browserInfo = getBrowser()
        if browserInfo == None: 
            raise APIException("All browsers busy")
    try:
        data, contentType, finalUrl, isMultiPage, sessionID = await routine.do(
            fmt=req.format, 
            extraction=req.extraction, 
            maxCacheAge=maxCacheAge, 
            debug=req.debug, 
            browser=browserInfo,
            sessionID=request.state.sessionID
        )
    except:
        raise 
    finally:
        if browserInfo:
            returnBrowser(browserInfo.id)

    headers = { "X-Session-ID": request.state.sessionID }
    if req.debug: 
        headers["X-Debug-URL"] = serverName + f"/debug/{sessionID}"
    if req.includeMeta:
        return Response(
            json.dumps({
                "contentType": contentType, 
                "finalUrl": finalUrl, 
                "isMultiPage": isMultiPage, 
                "data": data}), 
            media_type="application/json; charset=utf-8",
            headers=headers
        )
    else:
        return Response(data, media_type=contentType, headers=headers)
