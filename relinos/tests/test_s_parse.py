import unittest
import json

from relinos.parse import parseHtml

class TestParse(unittest.TestCase):
    def testParse(self) -> None:
        with open("testdata/parse/google.html") as f:
            htmlStr = f.read()

        with open("testdata/parse/google.json") as f:
            xPathSchemaStr = f.read()

        res, err = parseHtml(htmlStr, xPathSchemaStr)
        if err: raise err

        #self.debug(json.dumps(res, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    unittest.main()
