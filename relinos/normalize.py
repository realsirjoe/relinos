from typing import Any, cast
import json
import re
import hashlib
from urllib.parse import urlparse

from relinos.tools import generateSignature
from importlib.resources import files

import logging
logger = logging.getLogger(__name__)

class AmbiguousDataError(Exception):
    pass

def getLocaleToNrFormat() -> dict[str, str]:
    path = files("relinos").joinpath(
        "data/norm_locale_number_format.json"
    )
    with path.open() as f:
        return cast(dict[str, str], json.loads(f.read()))

def getCurrencyVariables() -> tuple[ dict[str, set[str]], dict[str, set[str]], str ]:
    '''Returns currency lookup tables and regex'''
    filepath = files("relinos").joinpath("data/norm_currencies.csv")

    allSymbols = []
    currencyCodeToSymbols = {}
    symbolToCurrencyCodes: dict[str, set[str]] = {}

    with filepath.open() as f:
        rows = f.read().splitlines()[1:] # skips header
    
    for row in rows:
        row = row.strip("\n").strip("\r")
        columns = row.split(",")
        if not columns or not columns[0]: 
            raise AmbiguousDataError(f"{filepath} has invalid format, first column of each row must be a currencyCode")

        currencyCode = columns[0].strip()

        columns = list(set([c.strip() for c in columns if c]))
        currencyCodeToSymbols[currencyCode] = set(columns)
        allSymbols += columns

    # building reverse lookup
    for currencyCode, symbols in currencyCodeToSymbols.items():
        for symbol in symbols:
            if symbol not in symbolToCurrencyCodes:
                symbolToCurrencyCodes[symbol] = set()
            symbolToCurrencyCodes[symbol].add(currencyCode)

    # building currency regex order by length important to guarantee longest match
    allSymbols = sorted(list(set(allSymbols)), key=lambda s: (-len(s), s))
    pattern = "|".join(re.escape(s) for s in allSymbols)

    return currencyCodeToSymbols, symbolToCurrencyCodes, pattern

def getCountryCodeToCurrencyCode() -> dict[str, str]:
    path = files("relinos").joinpath("data/norm_country_code_currency_code.csv")
    with path.open() as f:
        rows = f.read().splitlines()

    countryCodeToCurrencyCode = {}
    for row in rows:
        row = row.strip("\n").strip(" ")
        cols = row.split(",")
        countryCodeToCurrencyCode[cols[0]] = cols[1]
    return countryCodeToCurrencyCode

nrFormatEnglish = "nrFormatEnglish"
nrFormatGerman = "nrFormatGerman"

localeToNrFormats = getLocaleToNrFormat()
countryCodeToCurrencyCode = getCountryCodeToCurrencyCode()

currencyCodeToSymbols, symbolToCurrencyCodes, reCurrency = getCurrencyVariables()

def keyCounts(data: dict[Any, Any] | list[Any]) -> tuple[int, int, float]:
    '''
    Input: a json like structure
    Output:
        keyCount: counts recursively all keys
        nonEmptyKeyCount: currently empty strings are not considered as empty
        coverageRatio
    '''
    keyCount = 0
    nonEmptyKeyCount = 0

    def walk(data: Any) -> None:
        nonlocal keyCount, nonEmptyKeyCount
        if isinstance(data, dict):
            for key, value in data.items():
                keyCount += 1
                # "" does not count as empty for now
                isNonEmpty = (
                    value is not None and 
                    value != [] and value != {}
                )
                if isNonEmpty: nonEmptyKeyCount += 1
                walk(value)
        elif isinstance(data, list):
            for value in data:
                walk(value)
    walk(data)

    coverageRatio = nonEmptyKeyCount/keyCount if keyCount else 0
    return keyCount, nonEmptyKeyCount, coverageRatio

def dataSignature(data: Any) -> str:
    '''
    If data changes the signature changes
    On dicts key order does not matter
    Arrays of different order are not equal
    '''
    payload = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def removeEmptyFields(obj: Any, allEmptyValues:bool = False) -> Any:
    '''
    By default removes only all fully empty list elements e.g. 
        A list element is considered empty if it is {}, [], None, "" or a dict and all its children are empty ( recursive )
        [10, 2, None] = [10, 2]
        [10, 2, {}] = [10, 2]
        [{"name": "Peter", "age": None}, {"name": None, "age": None}] = [{"name": "Peter", "age": None}]

    allEmptyValues=True will remove all key:value pairs with an empty value
        e.g.
        [{"name": "Peter", "age": None}, {"name": None, "age": None}] = [{"name": "Peter"}]
    '''
    emptyValues: list[Any] = [{}, [], None, ""]
    if isinstance(obj, dict):
        # recursive dfs
        cleaned = { k: removeEmptyFields(v, allEmptyValues) for k, v in obj.items() }

        isEmptyDict = True
        for v in cleaned.values():
            if v not in emptyValues: isEmptyDict = False
        if isEmptyDict: return {}

        return {
            k: v for k, v in cleaned.items()
            if not allEmptyValues or (v not in emptyValues)
        }
    if isinstance(obj, list):
        cleanedLst = [removeEmptyFields(v, allEmptyValues) for v in obj]
        return [
            v for v in cleanedLst 
            if v not in emptyValues
        ]

    # important otherwise possible pass by reference obj get passed directly instead of copied
    if not isinstance(obj, str) and not isinstance(obj, int) and not isinstance(obj, float) and obj != None:
        raise TypeError(f'removeEmptyFields invalid field type "{type(obj)}"')
    return obj

reGermanNumber = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
reEnglishNumber = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
reNumber = r"(?:(?P<englishNr>" + reEnglishNumber + ")|(?P<germanNr>" + reGermanNumber + "))"
rePriceLeft = r"(?P<currency>" + reCurrency + ")[ ]?(?P<amount>" + reNumber + ")"
rePriceRight = r"(?P<amount>" + reNumber + ")[ ]?(?P<currency>" + reCurrency + ")"

def normalizeNr(numberStr: str, locale: str="") -> tuple[float, bool, Exception|None]:
    """
    Numbers often use grouping separators for thousands and decimal separators for fractions.

    Commonly:
        - English-style: 1,000.50
        - German/French-style: 1.000,50

        This parser intentionally ignores spaces as separators, even though some
        locales use them, because they may create more false positives in free text.

        "'" is savely removed before checking since it is only used as a visual seperator if at all

        Rules:
        1. If both "," and "." appear, treat the last occurring separator as the decimal separator.
        Example:
           1,000.00  -> "." is decimal
           48.000,41 -> "," is decimal

        2. If only one separator type appears multiple times, treat it as a grouping separator,
           unless locale/context says otherwise.
       Example:
           1,000,000
           1.000.000

        3. If exactly one separator appears:

        - If the trailing group has != 3 digits, treat it as decimal.
        Example:
            1.00
            1,56
            12.3456

        - If the trailing group has exactly 3 digits, it is ambiguous.
        Example:
            1,000
            483.000
        These require locale or context.

        4. Indian numbering is special: the rightmost group has 3 digits, then groups of 2 digits
        to the left, e.g. 1,23,456.

    """
    locale = locale.replace("_", "-")

    isAmbigous = False
    numberStr = numberStr.strip()

    # remove optional visual seperator swiss style
    numberStr = re.sub(r"(?<=\d)'(?=\d)", "", numberStr)

    m = re.fullmatch(reNumber, numberStr)
    if not m: return 0, False, None
    m0 = m.group("englishNr")
    m1 = m.group("germanNr")
    if m0:
        # ambiguous nrs matched with english nr since it appears first in regex 
        # only one "." zero "," and tail after seperator is len 3
        if m0.count(".") == 1 and m0.count(",") == 0 and len(m0.rsplit(".", 1)[-1]) == 3:
            isAmbigous = True
            numberStr = m0
        elif m0.count(",") == 1 and m0.count(".") == 0 and len(m0.rsplit(",", 1)[-1]) == 3:
            isAmbigous = True
            numberStr = m0
        else:
            numberStr = m0.replace(",", "")
    elif m1:
        numberStr = m1.replace(".", "").replace(",", ".")

    if isAmbigous:
        if not locale:
            return 0, False,  AmbiguousDataError(f"Ambigous nr {numberStr} and no locale specified")

        if locale not in localeToNrFormats:
            return 0, False, ValueError(f'Invalid locale "{locale}"')
        nrFormat = localeToNrFormats[locale]
        
        if nrFormat == nrFormatEnglish:
            numberStr = numberStr.replace(",", "")
        elif nrFormat == nrFormatGerman:
            numberStr = numberStr.replace(".", "").replace(",", ".")
        else:
            return 0, False, ValueError(f"Unsupported nrFormat: {nrFormat}")

    try:
        n = float(numberStr) 
        isNumber = True
    except:
        n = 0
        isNumber = False

    return n, isNumber, None

def normalizePrice(dataStr: str, locale: str="") -> tuple[str, float, bool, Exception|None]:
    '''
    Parses a currency symbol (triplet, unicode symbol, or mix) and an amount

    - currency symbol:
        A currency symbol may be unique for a currency like €, US$, RUB
        Or used by many currencies like $ which is used for US Dollars, HKD, SGD and many Pesos based currencies

        Unique currencies can be resolved without locale

    - amount:
        Amount utilizes normalizeNr 
    '''
    locale = locale.replace("_", "-")
    m = re.fullmatch(rePriceLeft, dataStr)
    if not m:
        m = re.fullmatch(rePriceRight, dataStr)
        if not m: return "", 0, False, None

    currency = m.group("currency")
    numberStr = m.group("amount")

    number, isNumber, error = normalizeNr(numberStr, locale)
    if error: return "", 0, False, error
    if not isNumber: return "", 0, False, None

    currencyCodes = list(symbolToCurrencyCodes.get(currency, {}))
    if not currencyCodes:
        return "", 0, False, ValueError(f'Unsupported currency symbol "{currency}"')

    isAmbiguous = len(currencyCodes) > 1
    # can resolve without locale
    if not isAmbiguous:
        return currencyCodes[0], number, True, None
    else:
        # try to resolve via locale
        if not locale:
            return "", 0, False,  AmbiguousDataError(
                f'No locale specified and currency "{currency}" is ambiguous, {len(currencyCodes)} countries use this symbol'
            )

        tmp = locale.split("-")
        # requires a countryCode
        if len(tmp) != 2 and len(tmp) != 3:
            return "", 0, False, ValueError(f'Invalid locale "{locale}"')

        countryCode = tmp[-1] # to not pick optional script accidently e.g. zh-Hant-HK
        currencyCode = countryCodeToCurrencyCode.get(countryCode)
        if not currencyCode:
            return "", 0, False, ValueError(f'Unsupported countryCode "{countryCode}"')

        countrySymbols = currencyCodeToSymbols[currencyCode]
        if currency not in countrySymbols:
            return "", 0, False, ValueError(f'Unsupported currency "{currency}" for countryCode "{countryCode}"')

        return currencyCode, number, True, None

def normalizeDomain(domain: str) -> str:
    return domain.removeprefix("www.")

def urlToDomain(url: str) -> str:
    return normalizeDomain(urlparse(url).netloc)

def normalizeDict(obj: Any, keepOriginal:bool=True, toCurrency: str = "", locale: str = "") -> tuple[Any, Exception|None]:
    '''
    Automatically parses prices and soon other fields

    keepOriginal=False: deletes original raw value and only keeps parsed version ( on successful parse )
    toCurrency: converts prices to specified currency code e.g. USD, GBP, CNY, EUR, ...
    '''
    if toCurrency: return None, NotImplementedError("toCurrency is currently unsupported")

    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            v, err = normalizeDict(v, keepOriginal, toCurrency, locale=locale)
            if err: return None, err
            cleaned[k] = v

            if isinstance(v, str):
                currency, amount, isPrice, err = normalizePrice(v, locale=locale)
                if err: return None, err 
                if isPrice:
                    cleaned[k + ":::currency"] = currency
                    cleaned[k + ":::amount"] = amount
                    if not keepOriginal: del cleaned[k]
                    continue
        return cleaned, None
    if isinstance(obj, list):
        cleanedLst = []
        for v in obj:
            v, err = normalizeDict(v, keepOriginal, toCurrency, locale=locale)
            if err: return None, err
            cleanedLst.append(v)
        
        return cleanedLst, None

    # important otherwise possible pass by reference obj get passed directly instead of copied
    if not isinstance(obj, str) and not isinstance(obj, int) and not isinstance(obj, float) and obj != None:
        return None, TypeError(f'normalizeDict invalid field type "{type(obj)}"')

    return obj, None

def fuseData(arr: list[Any]) -> tuple[Any, bool]:
    """
    Tries to connect related parallel data.

    Rules:
    - None values are ignored
    - dict1 + dict2: recursively merge by key ( may discard dict2 values )
    - list + list: append and deduplicate ( stops recursion )
    - value + value: 
        if same: return value, False
        if more than 1: return first, True

    Output: 
        fusedData: Any
        hasConflictingData: bool 
    """
    
    arr = [el for el in arr if el is not None]
    if len(arr) == 0: return None, False
    if len(arr) == 1: return arr[0], False

    types = {type(el) for el in arr}
    if len(types) > 1: 
        raise ValueError(f"fuseData: cannot merge parallel items of different types '{types}'")

    if isinstance(arr[0], dict):
        data = {}
        hasConflictingData = False

        keys = [key for data in arr for key in data.keys()]
        keys = list(dict.fromkeys(keys)) # deduplicate
        for key in keys:
            values = [item.get(key) for item in arr]
            data[key], conflict = fuseData(values)
            hasConflictingData = hasConflictingData or conflict

        return data, hasConflictingData
    elif isinstance(arr[0], list):
        signatures = set()
        newArr = []
        for subArr in arr:
            for el in subArr:
                elSignature = generateSignature(el)
                if elSignature in signatures:
                    continue

                signatures.add(elSignature)
                newArr.append(el)

        return newArr, False
    else:
        deduped = list(dict.fromkeys(arr))
        if len(deduped) == 1: return deduped[0], False

        logging.warning(f"fuseData: conflicting scalar values, using first of {deduped}")
        return deduped[0], True
