from typing import Any
import unittest
from dataclasses import dataclass
import time

from relinos.tools import serialize, deserialize, createPdfFromFolder

class Human:
    name: str
    parent: Human|None

    def __init__(self, name: str, parent: Human|None = None):
        self.name = name
        self.parent=parent

@dataclass
class SamplePerson:
    firstName: str
    lastName: str
    age: int

@dataclass
class SampleBook:
    name: str
    description: str
    author: SamplePerson
    
# non dataclass classes with initializer are also supported 
# if args have same names as type hints
class SamplePerson2:
    firstName: str
    lastName: str
    age: int

    def __init__(self, firstName: str, lastName: str, age: int = 0):
        self.firstName = firstName
        self.lastName = lastName
        self.age = age

# typehints are required
class PersonNoTypeHints:
    def __init__(self, firstName: str, lastName: str, age: int):
        self.firstName = firstName
        self.lastName = lastName
        self.age = age

class EmptyClass:
    pass

class TupleClass:
    d: list[tuple[str, int]]
    def __init__(self, d: list[tuple[str, int]]):
        self.d = d

class TestTools(unittest.TestCase):
    def testSerialize(self) -> None:
        h1 = Human("Peter")
        h2 = Human("Alex")
        h1.parent = h2
        h2.parent = h1
        
        try:
            serialize(h1)
        except RecursionError as e:
            pass
        else:
            with self.subTest():
                raise AssertionError("Should have raised RecursionError for obj with cycle")

        tests = [
            (Human("Peter", Human("Alex")), {"name": "Peter", "parent": {"name": "Alex", "parent": None}}),
            ({"name": "Peter", "age": 10}, {"name": "Peter", "age": 10}),
        ]
        for obj, expectedOut in tests:
            res = serialize(obj)
            if expectedOut != res:
                with self.subTest():
                    raise AssertionError("obj of type '{type(obj)}' failed to correctly serialize")

        failTests = [
            # cannot serialize non 'str' dict keys
            {1: "helo"}
        ]
        for i, obj in enumerate(failTests):
            try:
                serialize(obj)
            except:
                pass
            else:
                with self.subTest():
                    raise AssertionError(f"Error should have been raised for serialize on failTests[{i}]")

    def testDeserialize(self) -> None:
        tests: list[tuple[type[Any], Any, Any]] = [
            # simple object
            (SamplePerson, {"firstName": "Will", "lastName": "Durant", "age": 50}, SamplePerson("Will", "Durant", 50)),
            # save casting
            (SamplePerson, {"firstName": "Will", "lastName": "Durant", "age": "50"}, SamplePerson("Will", "Durant", 50)),
            # skipping optional arg age 
            (SamplePerson2, {"firstName": "Will", "lastName": "Durant"}, SamplePerson2("Will", "Durant", 0)),
            # None serialization
            (Human, {"name": "Will", "parent": None}, Human("Will")),
            # positional obj parsing
            (Human, ["Will", None], Human("Will")),
            (SamplePerson, ["Will", "Durant", 50], SamplePerson("Will", "Durant", 50)),
            # nested object
            (
                SampleBook, 
                {
                "name": "The Age of Napoleon", 
                "description": "In this masterful work, listeners will encounter the French Revolution and its leaders Danton, Desmoulins, Robespierre, and Saint-Just; Napoleon's meteoric rise from provincial Corsican military student to emperor and commander of the largest army in history", 
                "author": {"firstName": "Will", "lastName": "Durant", "age": 50}
                }, 
                SampleBook(
                    name="The Age of Napoleon", 
                    description="In this masterful work, listeners will encounter the French Revolution and its leaders Danton, Desmoulins, Robespierre, and Saint-Just; Napoleon's meteoric rise from provincial Corsican military student to emperor and commander of the largest army in history", 
                    author=SamplePerson("Will", "Durant", 50)
                ),
            ),
            (SamplePerson2, {"firstName": "Will", "lastName": "Durant", "age": 50}, SamplePerson2("Will", "Durant", 50)),
        ]
        for tCls, tDict, expectedOut in tests:
            res = deserialize(tCls, tDict)
            if expectedOut.__dict__ != res.__dict__:

                with self.subTest():
                    raise AssertionError(
                        f"dict failed to correctly deserialized into type '{tCls}'" + 
                        f"got {res.__dict__} expected {expectedOut.__dict__}"
                    )

        failTests: list[tuple[type[Any], Any]] = [
            # type hints are required for deserialization
            (PersonNoTypeHints, {"firstName": "Will", "lastName": "Durant", "age": 50},),

            # only simple datatypes allowed
            (SampleBook, {"name": "Odyssey", "description": "", "author": SamplePerson("Homer", "", 50)},),

            # class has no type hints, raises error 
            (EmptyClass, {}),

            # unsave cast
            (SamplePerson, {"firstName": "Will", "lastName": "Durant", "age": "50.0"}),

            # impossible cast
            (SamplePerson, {"firstName": "Will", "lastName": "Durant", "age": "blabla"}),

            # invalid param
            (SamplePerson, {"firstName": "Will", "lastName": "Durant", "age": 50, "birthyear": 1885}),

            # skipping required attribute firstName
            (SamplePerson, {"lastName": "Durant", "age": 50},),

            # positional obj parsing not enough attributes
            (SamplePerson, ["Will", "Durant"]),

            # tuple value 2 is invalid type
            (TupleClass, {"d": [["v1", "v2"]]}),

            # on parsing lists as class objects even attributes 
            # with defaults need to be specified to avoid danger
            # invalid, missing age
            (SamplePerson2, ["Will", "Durant"]),
        ]
        for i, t in enumerate(failTests):
            try:
                res = deserialize(t[0], t[1])
            except Exception as e:
                pass
            else:
                with self.subTest():
                    raise AssertionError(f"Error should have been raised for deserialize on failTests[{i}]")

    def testCreatePdfFromFolder(self) -> None:
        maxDuration = 0.5

        startTime = time.monotonic()
        createPdfFromFolder("testdata/tools/pdfFromFolder", outputPath = "/tmp/pdfFromFolderOut.pdf")
        duration =  time.monotonic() - startTime
        if duration > maxDuration:
            raise AssertionError(f"createPdfFromFolder took longer than max duration {maxDuration}s")

if __name__ == "__main__":
    unittest.main()
