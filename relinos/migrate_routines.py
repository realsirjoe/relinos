# Migrates all v0.2.x routines inside ~/.relinos to the new standard.
# v0.3 routines are easier to read and write, v0.2 routines are discontinued.
# Read more about v0.3 routines in README.md

from typing import Any
import json
from pathlib import Path
import re

from relinos.scraping_api import searchRoutines, transformMap, Routine, sha1, addRoutine, validRoutineParamName
from relinos.tools import deserialize, serialize
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

def updateRoutineV1(routine: dict) -> dict:
    supportedTopLevelKeys = ["url", "actions", "pagination"]

    if routine.get("pagination"):
        routine["pagination"]["maxPages"] = str(routine["pagination"]["maxPages"])

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


    for p in routine["params"]: del p["patches"] # deleting legacy 'patches' key
    routine["version"] = "0.3"

    return routine

def updateRoutineV2(routine: dict) -> dict:
    paramsMap = { p["name"]: p for p in routine["params"] }
    if len(paramsMap) != len(routine["params"]):
        raise Exception("Duplicate parameter names, fix first")

    for key in paramsMap.keys():
        del paramsMap[key]["name"]

    routine["params"] = paramsMap
    routine["version"] = "0.4"

    return routine
    
def main():
    for r in searchRoutines("", limit=-1):
        print(f"Converting {r['name']}")
        id = sha1("r_" + r["name"])
        routinePath = Path(storageDirPath) / id[:2] / id[2:] / "000.json"
        print(routinePath)

        with open(routinePath) as f: rawRoutine = json.loads(f.read())
        if rawRoutine.get("version", "") == "0.4": 
            print("already converted")
            continue

        if not rawRoutine.get("version"): # v1 has no version nr
            rawRoutine = updateRoutineV1(rawRoutine)

        if rawRoutine["version"] == "0.3": # v2 has version of relinos
            rawRoutine = updateRoutineV2(rawRoutine)

        # deserialize it to newest version
        try:
            routine: Routine = deserialize(Routine, rawRoutine)
        except:
            raise Exception("Internal Error, Malformed routine")

        #print(json.dumps(serialize(routine), indent=4, ensure_ascii=True))
        addRoutine(routine, True)

        print("----")

if __name__ == "__main__":
    main()
