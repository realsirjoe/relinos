# Migrates all v0.2.x routines inside ~/.relinos to the new standard.
# v0.3 routines are easier to read and write, v0.2 routines are discontinued.
# Read more about v0.3 routines in README.md

from typing import Any
import json
from pathlib import Path
import re

from relinos.scraping_api import searchRoutines, transformMap, Routine, sha1, addRoutine, validRoutineParamName
from relinos.tools import deserialize
from relinos.config import storageDirPath

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

def updateRoutine(routine: dict) -> Routine:
    supportedTopLevelKeys = ["url", "actions", "pagination"]

    paramsMap = { p["name"]: p for p in routine["params"] }
    if len(paramsMap) != len(routine["params"]):
        raise Exception("Duplicate parameter names, fix first")

    adjustments: dict[str, int] = {}
    for k in paramsMap.keys():
        paramName = paramsMap[k]["name"]
        if not re.fullmatch(validRoutineParamName, paramName):
            raise Exception(f"Change param name {paramName}, only alphanumerics and '_' are valid")
        
        for p in paramsMap[k]["patches"]:
            if p["keypath"].split(".")[0] not in supportedTopLevelKeys:
                raise Exception(f"Invalid patch keypath {p['keypath']}")

            value = f"||{paramName}"
            if p['transform']: value += f":{p['transform']}"
            value += "||"

            if p['transform'] and p['transform'] not in transformMap:
                raise Exception(f"Unknown transform '{p['transform']}' for param '{p['keypath']}'")

            adjustment = adjustments.get(p['keypath'], 0)
            # danger if value is a reference type
            success = setNestedAttr(routine, p["keypath"], value, p["start"]+adjustment, p["end"]+adjustment)
            if not success: raise Exception(f"Unable to set routine attribute with keypath '{p['keypath']}'")

            # start and end patch positions are based on an attributes initial length 
            # so we need to adjust after changing an attribute
            oldLen = p["end"] - p["start"]
            newLen = len(value)
            adjustments[p["keypath"]] = adjustments.get(p["keypath"], 0) + (newLen - oldLen)
    try:
        for p in routine["params"]: del p["patches"] # deleting legacy 'patches' key
        routineCopy: Routine = deserialize(Routine, routine)
    except:
        raise Exception("Internal Error, Malformed routine")

    return routineCopy

def main():
    for r in searchRoutines("", limit=-1):
        print(f"Converting {r['name']}")
        id = sha1("r_" + r["name"])
        routinePath = Path(storageDirPath) / id[:2] / id[2:] / "000.json"

        with open(routinePath) as f: oldRoutine = json.loads(f.read())

        if oldRoutine.get("pagination"):
            oldRoutine["pagination"]["maxPages"] = str(oldRoutine["pagination"]["maxPages"])

        if oldRoutine.get("version"): print("Already converted")
        else:
            patchedRoutine = updateRoutine(oldRoutine)
            addRoutine(patchedRoutine, True)

        print("----")

if __name__ == "__main__":
    main()
