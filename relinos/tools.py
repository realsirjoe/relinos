import uuid
from typing import Any, get_args, get_type_hints, get_origin
import re
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
import html
import json
import logging
import hashlib
import types
import requests
import socket

logger = logging.getLogger(__name__)

def createPdfFromFolder(folderPath: str, outputPath: str = "output.pdf") -> None:
    '''
    Takes all images in a folder, orders them, and creates a pdf from them
    Pdf best balances small filesize with convenient usage

    Gif was convenient to use on osx but didn't compress images well
    Webp compressed perfect but one couldnt select single images and just view animation in a web browser 
    Tiff had terrible compression
    Mp4 okay compression but hard to navigate frames and needs many dependencies
    Pdf good compression, easy to view on any device and os
    '''

    # Get and sort all image files from the directory
    validExtensions = (".png", ".jpg", ".jpeg")
    files = [f for f in os.listdir(folderPath) if f.lower().endswith(validExtensions)]
    if len(files) == 0:
        logging.info(f"No matching images found in: {folderPath}")
        return

    files.sort()  # This correctly orders screenshot_01, screenshot_02, etc.

    # Resize and format images
    images = []
    for filename in files:
        origImage = Image.open(os.path.join(folderPath, filename))

        # Decrease image size by half
        image = origImage.resize(
            (origImage.width // 2, origImage.height // 2),
            Image.Resampling.BICUBIC,
        )

        # Add a black border to better distinguish between screenshots
        image = ImageOps.expand(image, border=40, fill="black")

        images.append(image)

    if images:
        images[0].save(
            outputPath,
            save_all=True,
            append_images=images[1:],
            format="PDF",
        )

def addCaption(imagePath: str, text: str, outputPath: str = "") -> None:
    if not outputPath: outputPath = imagePath 

    origImg = Image.open(imagePath).convert("RGB")
    origWidth, origHeight = origImg.size

    # Calculate font and caption bar height
    fontSize = int(origWidth * 0.020)
    # 15 % of image height added extra space at bottom
    captionHeight = int(origHeight * 0.15)  

    font: Any
    try:
        font = ImageFont.truetype("arial.ttf", fontSize)
    except IOError:
        font = ImageFont.load_default(size=fontSize)

    # Create a new blank canvas (Same width, but taller)
    newHeight = origHeight + captionHeight
    newImg = Image.new("RGB", (origWidth, newHeight), color=(0, 0, 0))

    # Paste the original screenshot at the very top (0, 0)
    newImg.paste(origImg, (0, 0))

    # Draw text centered in the bottom caption bar
    draw = ImageDraw.Draw(newImg)

    # Calculate centering coordinates
    textY = origHeight + 20  # Slight offset adjustment
    textX = 30

    # Draw the text (White text on black background)
    draw.text((textX, textY), "\n".join(textwrap.wrap(text, width=90, break_long_words=True)), fill=(255, 255, 255), font=font)

    newImg.save(outputPath)

def addRedBorder(imagePath: str, outputPath: str = "", borderWidth: int = 10) -> None:
    if not outputPath: outputPath = imagePath

    img = Image.open(imagePath).convert("RGB")
    img = ImageOps.expand(img, border=borderWidth, fill="red")
    img.save(outputPath)

    logging.debug(f"Saved bordered image to: {outputPath}")

def createHtmlPagesViewer(htmlStrs: list[str]) -> str:
    """
    Puts multiple html pages into one html page via iframes for easily viewing them
    """
    combined = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {
        background: #EEEEEE;
    }
    iframe {
        width: 100%;
        height: 1080px;
        border: 2px solid lightgrey;
        margin-bottom: 20px;
    }
    </style>

    <script type="application/javascript">
    function resizeIFrameToFitContent( iFrame ) {
        iFrame.style.height = String(iFrame.contentWindow.document.body.parentElement.scrollHeight) + "px";
    }

    window.addEventListener('DOMContentLoaded', function(e) {
        // giving pages some time to load 
        setTimeout(function () {
            var iframes = document.querySelectorAll("iframe");
            for( var i = 0; i < iframes.length; i++) {
                resizeIFrameToFitContent( iframes[i] );
            }
        }, 100);
    } 
    );
    </script>
    </head>
    <body>
    """
    for s in htmlStrs:
        combined += f'<iframe srcdoc="{html.escape(s)}"></iframe>'
    combined += "</body></html>"

    return combined

MAX_RECURSION_DEPTH = 10
def generateSignature(obj: Any, depth: int = 0) -> str:
    """ 
    Generates a unique signature out of a any object 
    it doesnt care about type but data and structure itself

    Will error for datetime, uuid, and other types maybe use pickle instead
    """
    rawData: list[str]|dict[str, str]
    if depth >= MAX_RECURSION_DEPTH:
        raise Exception(f"Object too nested, max recursion depth {MAX_RECURSION_DEPTH}")
    if isinstance(obj, (tuple, list, set)):
        rawData = [generateSignature(subObj, depth + 1) for subObj in obj]
    elif type(obj) == dict:
        rawData = {key: generateSignature(value, depth + 1) for key, value in obj.items()}
    elif hasattr(obj, '__dict__') and not isinstance(obj, type):
        tmp = obj.__dict__
        rawData = {generateSignature(key, depth + 1): generateSignature(value, depth + 1) for key, value in tmp.items()}
    elif isinstance(obj, bytes):
        rawData = {
            "__bytes__": hashlib.sha256(obj).hexdigest() 
        }
    else:
        rawData = obj

    jsonString = json.dumps(rawData, sort_keys=True)
    h = hashlib.sha256(jsonString.encode('utf-8')).hexdigest()
    return h

def serialize(obj: Any, depth: int = 0) -> Any:
    """
    Serializes an object into JSON-compatible data.
    JSON-compatible data = bool, int, float, str, nested dicts, nested lists

    Non 'str' dict keys are not supported
    """

    # python would also throw RecursionError 
    # but max recursions is too high by default and 
    # function rather slow for this purpose
    maxRecursionDepth = 100
    if depth >= maxRecursionDepth:
        raise RecursionError(f"Could not serialize obj of type '{type(obj)}', contains cycle or too nested")

    if obj is None:
        return None

    # basic types
    elif isinstance(obj, (bool, int, float, str)):
        return obj

    # list, tuple, set
    elif isinstance(obj, (list, tuple, set)):
        return [serialize(x, depth=depth+1) for x in obj]

    # dict
    elif isinstance(obj, dict):
        for k in obj.keys():
            if not isinstance(k, str):
                raise ValueError("Only string dict keys are supported")
        return {
            serialize(k, depth=depth+1): serialize(v, depth=depth+1)
            for k, v in obj.items()
        }

    # custom class
    elif isinstance(obj, object) and type(obj).__module__ != "builtins":
        attributes = get_type_hints(type(obj))

        if not attributes:
            raise Exception(
                f"class '{type(obj)}' does not have type hints"
            )

        d = {}
        for key in attributes:
            if hasattr(obj, key):
                d[key] = serialize(getattr(obj, key), depth=depth+1)

        return d

    raise ValueError(f"Unsupported type '{type(obj)}'")

int_number_re = re.compile(r"-?\d+")
float_number_re = re.compile(r"-?\d+\.\d+")

def deserialize(cls: type[Any], data: Any, path: str = "") -> Any:
    """
    Deserializes JSON-compatible data into cls by using type hints
    Casts only when safe:
        Silently casts str to int only if in int format e.g. 4, 338, 10000, ...
        Silently casts str to float only if in float format e.g. 1.0, 3.01231, ... 

    not all attributes of an obj need to be in a dict if they are not required in its __init__ func
    Assumes type hint names and init func names are the same

    All relevant attributes need to have type hints on the class otherwise they will be missed

    Custom classes require data to be of type dict. 
    Custom classes require init arg names to match the obj arg names

    Currently only used for routine deserialization, but could be used for anything
    """

    # only basic types can be in serialized data
    supportedDataTypes = (bool, int, float, str, dict, list, tuple, set, type(None))
    if not isinstance(data, supportedDataTypes):
        raise Exception(
            f"Unsupported type '{type(data)}' for serialized data at {path} " +
            f"supported types '{supportedDataTypes}'"
        )
    
    if cls in [type(None)]:
        if isinstance(data, cls): 
            return data
        raise Exception(f"{path} of invalid type '{type(data)}', required '{cls}'")
    elif cls in [int, float]:
        if isinstance(data, cls):
            return data
        # only cast when save
        elif isinstance(data, str):
            if cls == int and int_number_re.fullmatch(data):
                return cls(data)
            elif cls == float and float_number_re.fullmatch(data):
                return cls(data)

        raise Exception(f"{path} of invalid type '{type(data)}', required '{cls}'")
    elif cls in [bool]:
        if isinstance(data, cls):
            return data
        raise Exception(f"{path} of invalid type '{type(data)}', required '{cls}'")
    elif cls in [str]:
        if isinstance(data, cls):
            return data
        elif isinstance(data, (int, float)):
            return cls(data)
        raise Exception(f"{path} of invalid type '{type(data)}', required '{cls}'")
    elif get_origin(cls) == types.UnionType:
        possibleClses = get_args(cls)
        for possibleCls in possibleClses:
            try:
                return deserialize(possibleCls, data, path=path)
            except Exception:
                pass

        # crafting error hint
        tmp = []
        for c in possibleClses:
            if c in [bool, int, float, str, type(None)]:
                tmp.append(str(c.__name__))
            else:
                tmp.append(
                    f"{c.__module__}.{c.__qualname__}({get_type_hints(c)})"
                )
        possibleClsesStr = ",".join(tmp)

        raise Exception(f"{path} unable to convert '{type(data)}', to any of '{possibleClsesStr}'")
    elif get_origin(cls) in [list, set]:
        if isinstance(data, (list, set,)):
            arr = []
            for i, rawValue in enumerate(data):
                value = deserialize(get_args(cls)[0], rawValue, path=path+f".[{i}]")
                arr.append(value)
            if get_origin(cls) == set:
                return set(arr)
            else:
                return arr
        raise Exception(f"{path} of invalid type {type(data)}', required '{cls}'")
    elif get_origin(cls) in [tuple]:
        if isinstance(data, (list, tuple,)):
            arr = []
            if len(data) != len(get_args(cls)):
                raise Exception(f"{path} unable to convert tuple, expects {len(get_args(cls))} elements")

            for i, rawValue in enumerate(data):
                value = deserialize(get_args(cls)[i], rawValue, path=path+f".[{i}]")
                arr.append(value)
            return tuple(arr)
        raise Exception(f"{path} of invalid type {type(data)}', required '{cls}'")
    elif get_origin(cls) in [dict]:
        if isinstance(data, dict):
            keyCls, valueCls = get_args(cls)
            d = {}
            for rawKey, rawValue in data.items():
                # * stands for key
                key = deserialize(keyCls, rawKey, path=path+"*"+str(rawKey))
                value = deserialize(valueCls, rawValue, path=path+"."+key)
                d[key] = value
            return d
        raise Exception(f"{path} of invalid type '{type(data)}', required '{cls}'")
    # catches anything user defined, including classes in libraries
    elif isinstance(cls, type) and cls.__module__ != "builtins":
        attributes = get_type_hints(cls)
        if not attributes: 
            raise Exception(f"class of type '{cls}' does not have any type hints")

        if isinstance(data, dict):
            for dataKey in data.keys():
                if dataKey not in attributes:
                    raise Exception(f"{path} contains unknown key {dataKey}, unable to parse {cls}")

            d = {}
            for key, attribCls in attributes.items():
                # does not check for missing keys here since some may be optional
                if key in data:
                    rawValue = data[key]
                    value = deserialize(attribCls, rawValue, path=path+"."+key)
                    d[key] = value
            # if non optional attributes are missing an error may be raised
            try:
                return cls(**d)
            except TypeError as e:
                raise

        elif isinstance(data, list):
            arr = []
            if len(attributes) != len(data):
                raise Exception(f"{path}, invalid nr of positional attributes, is {len(data)} want {len(attributes)}, unable to parse class '{cls}'")
            for i, attribCls in enumerate(attributes.values()):
                value = deserialize(attribCls, data[i], path=path+f".[{i}]")
                arr.append(value)
            try:
                return cls(*arr)
            except TypeError as e:
                raise

        raise Exception(f"{path} of invalid type '{type(data)}', required type '{dict}' to parse class '{cls}'")

    raise Exception(f"{path} of unsupported type '{type(data)}'")

def jsonToHtml(data: dict[str, Any]) -> str:
    """ Creates a json viewer html document"""
    def render(value: Any, key: str="") -> str:
        if isinstance(value, dict):
            children = "".join(
                f"""
                <div class="json-item">
                    <span class="key">{html.escape(str(k))}</span>:
                    {render(v)}
                </div>
                """
                for k, v in value.items()
            )

            return f"""
            <details open>
                <summary>{html.escape(str(key))} {{{len(value)}}}</summary>
                <div class="children">{children}</div>
            </details>
            """

        elif isinstance(value, list):
            if len(value) == 0: return "[]"
            children = "".join(
                f'<div class="json-item">{render(v, str(i))}</div>'
                for i, v in enumerate(value)
            )

            return f"""
            <details open>
                <summary>[{len(value)}]</summary>
                <div class="children">{children}</div>
            </details>
            """

        elif isinstance(value, str):
            return f'<span class="string">"{html.escape(value)}"</span>'

        elif isinstance(value, bool):
            return f'<span class="boolean">{str(value).lower()}</span>'

        elif value is None:
            return '<span class="null">null</span>'
        else:
            return f'<span class="number">{html.escape(str(value))}</span>'

    body = render(data)

    return """<!DOCTYPE html><html>
    <head><meta charset="utf-8"><title>JSON Viewer</title>
    <style>
    /* indentation */
    body { padding: 2rem 1rem; font-size: 1.4rem; }
    .json-viewer { line-height: 1.5; }
    details { margin-left: 20px; }
    .children { margin-left: 20px; }
    .json-item { margin: 3px 0; }

    /* expandable elements not selectable */
    summary { cursor: pointer; user-select: none; }

    /* color theme */
    body { font-family: monospace; background: white; }
    .key { color: #922; font-weight: bold; }
    .string { color: #080; }
    .number { color: #00c; }
    .boolean { color: #a0a; }
    .null { color: #777; }
    </style>
    </head>
    <body><div class="json-viewer">""" + body + "</div></body></html>"

def writeFileAtomic(filepath: str, data: str) -> None:
    """ 
    creates a .tmp file in the same directory, which may persist on failure
    """
    tmpFilepath = filepath + f".{uuid.uuid4().hex}.tmp"

    with open(tmpFilepath, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmpFilepath, filepath)

def parseFloat(value: str) -> tuple[float, Exception|None]:
    try:
        return float(value), None
    except Exception as e:
        return 0.0, e

def getPublicIP() -> str:
    ip = requests.get('https://api.ipify.org').content.decode('utf8')
    return ip

def getPrivateIP() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return str(ip)
