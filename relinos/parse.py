import json
import re
from urllib.parse import urlsplit, urlparse, urljoin

from lxml import html, etree

from relinos.markdown import htmlToMarkdown

class ParseException(Exception):
    pass

# strings that look like a path or url 
# won't get normalized in closestMatches the same way text would
def isUrlOrPath(s: str) -> bool:
    if not s or " " in s: return False

    p = urlparse(s)

    # Full URL
    if p.scheme in ("http", "https") and p.netloc:
        return True
    elif p.scheme:
        # Not a URL: reject other schemes (mailto:, ftp:, etc.)
        return False

    # Must have a non-empty path
    if not p.path: return False

    return True

def leafData(node: html.HtmlElement|str, extractAs: str = "") -> str:
    if isinstance(node, str):
        if extractAs in ["md", "html"]:
            raise Exception(f"Cannot extract data as {extractAs}, the xpath already selected a string")
        return node
    if extractAs == "md":
        return htmlToMarkdown(etree.tostring(node, encoding="unicode"), extractImages=False)
    elif extractAs == "html":
        return str(etree.tostring(node, encoding="unicode"))
    elif hasattr(node, "text_content"):
        data = " ".join(node.text_content().split())
        return data
    return " ".join(str(node).split())

def extractAll(xpathSchema: dict[str, JsonType], lxmlNode: html.HtmlElement, resolvingUrl: str = "", keypath: str = "") -> tuple[JsonType, Exception|None]:
    data: JsonType = {}
    isLeaf = True

    for key, xpathSchemaPart in xpathSchema.items():
        if key.startswith("$"): continue
        isLeaf = False

        assert isinstance(data, dict)

        if not isinstance(xpathSchemaPart, dict):
            return data, ParseException(f"{keypath} Invalid xpathschema of invalid type {type(xpathSchemaPart)}")

        xpath = xpathSchemaPart.get("$xpath")
        required = xpathSchemaPart.get("$required")
        if xpath:
            if not isinstance(xpath, str):
                return data, ParseException(f"{keypath} Invalid xpath of type{type(xpath)}")

            results: list[html.HtmlElement]|list[str] = lxmlNode.xpath(xpath)
            # make path absolute
            if "@href" in xpath or "@src" in xpath:
                results = [
                    urljoin(resolvingUrl, r) if r.startswith(("http:/", "https://", "/", "./")) and isUrlOrPath(r) else r
                    for r in results
                ]
        else:
            results = [lxmlNode]

        if xpathSchemaPart.get("$list"):
            arr = []
            for i, result in enumerate(results):
                child, err = extractAll(xpathSchemaPart, result, resolvingUrl=resolvingUrl, keypath=keypath + f".{key}.[{i}]" )
                if err: return data, err
                arr.append(child)
            data[key] = arr 
        elif len(results) > 0:
            child, err = extractAll(xpathSchemaPart, results[0], resolvingUrl=resolvingUrl, keypath=keypath + f".{key}")
            if err: return data, err
            data[key] = child
        else: 
            if required:
                return data, ParseException(f"{keypath}.{key}: required property is null")
            data[key] = None

    if isLeaf: 
        required = xpathSchema.get("$required")
        xpath = xpathSchema.get("$xpath")
        if xpath == "":
            if required:
                return data, ParseException(f"{keypath}: required property is null")
            return None, None
        extractAs = xpathSchema.get("$format", "")
        pattern = xpathSchema.get("$pattern")
        extract = xpathSchema.get("$extract")

        try:
            if not isinstance(extractAs, str):
                return data, ParseException(f"{keypath}: invalid $format of type {type(extractAs)}")
            data = leafData(lxmlNode, extractAs=extractAs)
        except Exception as e:
            return data, Exception(f"{keypath}: {e}")

        if pattern: 
            if not isinstance(data, str):
                return data, ParseException(f"{keypath}: $pattern only valid on leaf elements")
            if not isinstance(pattern, str):
                return data, ParseException(f"{keypath}: invalid $pattern of type {type(pattern)}")
            if not re.fullmatch(pattern, str(data)):
                return data, ParseException(f"{keypath}: '{str(data)[:47]}...' does not match pattern '{pattern}'")
        if extract:
            if not isinstance(extract, str):
                return data, ParseException(f"{keypath}: invalid $extract of type {type(extract)}")

            match = re.fullmatch(extract, str(data))
            if not match:
                return data, ParseException(f"{keypath}: '{str(data)[:47]}...' could not match $extract '{extract}'")

            data = match.group(1)
        return data, None
    else: 
        return data, None

def parseHtml(htmlStr: str, xpathSchema: str, resolvingUrl: str="") -> tuple[JsonType, Exception|None]:
    lxmlNode = html.fromstring(htmlStr)
    data = json.loads(xpathSchema)
    return extractAll(data, lxmlNode, resolvingUrl=resolvingUrl)

################### Scoring ######################

type JsonType = None|bool|int|float|str|list["JsonType"]|dict[str,"JsonType"]
def flattenJson(data: JsonType) -> list[tuple[str, None|bool|int|float|str]]:
    values = []
    def walk(data: JsonType, path: str = "") -> None:
        if isinstance(data, (list,set)):
            for i, el in enumerate(data):
                walk(el, path=f"{path}.{i}")
        elif isinstance(data, dict):
            for k, v in data.items():
                walk(v, path=f"{path}.{k}")
        else:
            values.append((path, data))
    walk(data)

    return values

def getCoverageScore(data: JsonType, weights: dict[str, float]|None=None) -> tuple[float, float]:
    """ Does not look for accuracy but only populated fields """
    score: float
    scores: list[float] = []

    leafScoreMap: dict[str, list[float]] = {} 
    for key, v in flattenJson(data):
        # normalizes key indices to be all 0
        key = ".".join(
            ["0" if part.isnumeric() else part 
            for part in key.split(".")]
        ) 
        score = 1 if v != None and str(v).strip() != "" else 0

        if key not in leafScoreMap: leafScoreMap[key] = []
        leafScoreMap[key].append(score)

    for key, values in leafScoreMap.items():
        score = sum(values)/len(values)

        if weights:
            keys = [k for k, v in weights.items() if k == key]
            keys.sort(key=lambda x: -len(x))
            if len(keys) == 0: score = 0
            else: score *= weights[keys[0]]

        scores.append(score)

    if len(scores) == 0: return 0, 0
    avg = sum(scores) / (len(weights) if weights else len(scores))
    return avg, sum(scores)

################### Other #######################

def generateUrlName(url: str) -> str:
    ''' 
    a url is often not enough to id action driven interactions
    But it could be quite sufficient if one used the final url after all actions
    '''
    parsed = urlsplit(url if "://" in url else f"https://{url}")
    path = parsed.path.rstrip("/")
    host = parsed.hostname or ""
    host = host.removeprefix("www.")
    return f"{host}{path}".replace("/", "_")
