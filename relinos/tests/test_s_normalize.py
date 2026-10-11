import unittest
import json
import re

from relinos.normalize import (
    keyCounts, dataSignature, removeEmptyFields, 
    reNumber, AmbiguousDataError, normalizeNr, normalizePrice, normalizeDict, fuseData
)
from relinos.tools import generateSignature

class TestNormalize(unittest.TestCase):
    def testStats(self) -> None:
        with open("testdata/normalize/mueller.json") as f:
            data = json.loads(f.read())

        # same but some leaf arrays have more entries and some strings have been changed to arrays ( which should not change the keyCount )
        with open("testdata/normalize/mueller_more_leaf_list_elements.json") as f:
            data2 = json.loads(f.read())

        # same but key order and array element order changed
        with open("testdata/normalize/mueller_diff_key_order.json") as f:
            data3 = json.loads(f.read())

        keyCount, nonEmptyKeyCount, _ = keyCounts(data)
        keyCount2, nonEmptyKeyCount2, _ = keyCounts(data2)
        signature = "6383813145d2d43d726cec7feec17eee64c453353e8b74290390879cface7399"
        
        with self.subTest():
            self.assertEqual(40, keyCount)
            self.assertEqual(27, nonEmptyKeyCount)
            self.assertEqual(40, keyCount2)
            self.assertEqual(27, nonEmptyKeyCount2)
            self.assertEqual(signature, dataSignature(data))
            self.assertEqual(signature, dataSignature(data3))

    def testRemoveEmptyListElements(self) -> None:
        with open("testdata/normalize/google.json") as f:
            data = json.loads(f.read())

        # 1. data verification
        keyCount, _, _ = keyCounts(data)

        dataCleaned1 = removeEmptyFields(data)
        keyCountCleaned1, _, _ = keyCounts(dataCleaned1)

        dataCleaned2 = removeEmptyFields(data, allEmptyValues=True)
        keyCountCleaned2, _, _ = keyCounts(dataCleaned2)
        
        with self.subTest():
            self.assertEqual(keyCount, 213)
            self.assertEqual(keyCountCleaned1, 66) # much less keys
            self.assertEqual(keyCountCleaned2, 36) # even less keys

    def testReNumber(self) -> None:
        numberTest = [
            ("10", "englishNr", True),
            ("10.0", "englishNr", True),
            ("1000.0", "englishNr", True),
            # ambiguous number (german or english unknown)
            ("100.001", "englishNr", True),
            ("1,000.0", "englishNr", True),
            ("10000,000.0", "englishNr", False),
            ("10,0", "germanNr", True),
            ("900000,0", "germanNr", True),
            ("9.00000,0", "germanNr", False),
            ("900.000,0", "germanNr", True),
            ("9000.000,0", "germanNr", False),
        ]
        for nrStr, groupName, isValid in numberTest:

            with self.subTest():
                m = re.fullmatch(reNumber, nrStr)
                g = None
                if m: g = m.group(groupName)

                v = g != None
                if isValid and not v:
                    raise AssertionError(f"{nrStr} is valid but no match was returned")
                elif not isValid and v:
                    raise AssertionError(f"{nrStr} is invalid but a match was returned")

    def testNormalizeNr(self) -> None:
        tests = [
            (("1",), (1.0, True, None)),
            (("3.14159265358",), (3.14159265358, True, None)),
            ((" 2 ",), (2.0, True, None)),
            (("1'234",), (1234.0, True, None)),
            (("   ",), (0, False, None)),
            ((" not number  ",), (0, False, None)),
            (("1234,0",), (1234.0, True, None)),

            # german nr both ',' and '.' used
            (("1.234,012",), (1234.012, True, None)),
            # english nr both ',' and '.' used
            (("1,234.012",), (1234.012, True, None)),
            # large number both ',' and '.' used 
            (("1,000,234.012",), (1000234.012, True, None)),
            # multi seperators same symbol
            (("1,000,000",), (1000000, True, None)),
            (("1.000.000",), (1000000, True, None)),

            # one seperator but tail != 3
            (("1,00",), (1.00, True, None)),
            (("1.00",), (1.00, True, None)),
            (("1.0034",), (1.0034, True, None)),

            # one seperator tail == 3
            (("1,003","en-US"), (1003, True, None)),
            (("1,003","de-AT"), (1.003, True, None)),
            # country same but language difference
            (("1,003","en-CA"), (1003, True, None)),
            (("1,003","fr-CA"), (1.003, True, None)),
            (("1,003","de-CH"), (1003, True, None)),

            # Invalid grouping
            (("12,34,567", "en-US"), (0, False, None)),

            # Ambiguous and no locale
            (("134,567",), (0, False, AmbiguousDataError())),
            # unsupported locale but not used because inferred
            (("1234,567", "ar-IQ"), (1234.567, True, None)),
            # unsupported locale
            (("134,567", "ar-IQ"), (0, False, ValueError())),
            # invalid locale
            (("134,567", "en-XX"), (0, False, ValueError())),
            (("134,567", "xx-US"), (0, False, ValueError())),
        ]
        for inp, expected in tests:
            with self.subTest(inp=inp):
                out = normalizeNr(*inp)
                self.assertEqual(out[:2], expected[:2])
                self.assertIsInstance(out[2], type(expected[2]))
     
    def testNormalizePrice(self) -> None:
        # last out param is not checked for equality but isInstance
        tests = [
            # no currencies
            (("some text","",), ("", 0, False, None)),
            (("not a currency","en-US",), ("", 0, False, None)),
            (("12x","",), ("", 0, False, None)),
            (("12$$","",), ("", 0, False, None)),
            # currency left and right not valid
            (("$12$","",), ("", 0, False, None)),
    
            # locale specified
            (("$10.01","en-US",), ("USD", 10.01, True, None)),
            (("$10.01","en-someScript-US",), ("USD", 10.01, True, None)),

            # currency can be inferred
            (("HK$ 10.01","",), ("HKD", 10.01, True, None)),
            (("10.99€",),       ("EUR", 10.99, True, None)),

            (("10,99€",),       ("EUR", 10.99, True, None)),
            (("10.000,99€",),   ("EUR", 10000.99, True, None)),
            (("10,000.99€",),   ("EUR", 10000.99, True, None)),

            # locale not used (€ only used for EUR) parsing success
            (("10,000.99€","en-US"),   ("EUR", 10000.99, True, None)),

        
            # USD for de-AT locale invalid
            (("$10.01","de-AT"), ("", 0, False, ValueError())),
            # ambigous currency
            (("$10.01",), ("", 0, False, AmbiguousDataError())),
            (("10.01£",), ("", 0, False, AmbiguousDataError())),
            # unknown locale
            (("10.01£","xx-ES"), ("", 0, False, ValueError())),
            # invalid locale
            (("10.01£","de-Munda-AT-other"), ("", 0, False, ValueError())),

            # ambigous currency invalid locale
            (("10.001£","xx-XX"), ("", 0, False, ValueError())),
            
            # ambigous currency invalid country code
            (("10.01£","de-XX"), ("", 0, False, ValueError())),
        ]

        for inp, expected in tests:
            with self.subTest(inp=inp):
                out = normalizePrice(*inp)
                self.assertEqual(out[:3], expected[:3])
                self.assertIsInstance(out[3], type(expected[3]))

    def testNormalizeDict(self) -> None:
        with open("testdata/normalize/mueller.json") as f:
            data = json.loads(f.read())
            dataNormalized, err = normalizeDict(data, keepOriginal=False)
            if err:
                raise AssertionError(f"Could not normalizeDict: {str(err)}")

            keyCount, _, _ = keyCounts(data)
            keyCount2, _, _ = keyCounts(dataNormalized)
            with self.subTest():
                self.assertEqual(keyCount, 40)
                # added amount, currency field, removed price field
                self.assertEqual(keyCount2, 45)

    def testMergeDicts(self) -> None:
        with open("testdata/normalize/merge_google_p0.json") as f:
            htmlStr = f.read()
        fusedData, _ = fuseData([json.loads(htmlStr), json.loads(htmlStr)])
        fusedSignature = generateSignature(removeEmptyFields(fusedData))
        signature = generateSignature(removeEmptyFields(json.loads(htmlStr)))
        if fusedSignature != signature:
            raise AssertionError("fuseData behaves incorrectly on fusing two identical items")

        googleData = []
        for i in range(3):
            with open(f"testdata/normalize/merge_google_p{i}.json") as f:
                googleData.append(json.loads(f.read()))
        result, _ = fuseData(googleData)

        self.assertEqual(len(result["results"]), 28)

if __name__ == "__main__":
    unittest.main()
