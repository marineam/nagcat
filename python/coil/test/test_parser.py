"""Tests for coil.parser."""

import os
import unittest
from coil import parser, struct, parse_file, errors

class BasicTestCase(unittest.TestCase):

    def testEmpty(self):
        root = parser.Parser([""]).root()
        self.assert_(isinstance(root, struct.Struct))
        self.assertEquals(len(root), 0)

    def testSingle(self):
        root = parser.Parser(["this: 'that'"]).root()
        self.assertEquals(len(root), 1)
        self.assertEquals(root['this'], "that")

    def testMany(self):
        root = parser.Parser(["this: 'that' int: 1 float: 2.0"]).root()
        self.assertEquals(len(root), 3)
        self.assertEquals(root['this'], "that")
        self.assert_(isinstance(root['int'], int))
        self.assertEquals(root['int'], 1)
        self.assert_(isinstance(root['float'], float))
        self.assertEquals(root['float'], 2.0)

    def testStruct(self):
        root = parser.Parser(["foo: { bar: 'baz' } -moo: 'cow'"]).root()
        self.assert_(isinstance(root['foo'], struct.Struct))
        self.assertEquals(root['foo']['bar'], "baz")
        self.assertEquals(root.get('foo.bar'), "baz")
        self.assertEquals(root.get('@root.foo.bar'), "baz")
        self.assertEquals(root['-moo'], "cow")

    def testExtends(self):
        root = parser.Parser(["a: {x: 'x'} b: { @extends: ..a }"]).root()
        self.assertEquals(root['b']['x'], "x")

    def testRefrences(self):
        root = parser.Parser(["a: 'a' b: a x: { c: ..a d: =..a }"]).root()
        self.assertEquals(root['a'], 'a')
        self.assertEquals(root['b'], 'a')
        self.assertEquals(root.get('x.c'), 'a')
        self.assertEquals(root.get('x.d'), 'a')

    def testDelete(self):
        root = parser.Parser(["a: {x: 'x' y: 'y'}"
                              "b: { @extends: ..a ~y}"]).root()
        self.assertEquals(root['b']['x'], "x")
        self.assertRaises(KeyError, lambda: root['b']['y'])

    def testFile(self):
        path = os.path.join(os.path.dirname(__file__), "simple.coil")
        root = parser.Parser(["@file: %s" % repr(path)]).root()
        self.assertEquals(root.get('x'), "x value")
        self.assertEquals(root.get('y.z'), "z value")

    def testFileSub(self):
        path = os.path.join(os.path.dirname(__file__), "simple.coil")
        root = parser.Parser(["sub: { @file: [%s 'y']}" % repr(path)]).root()
        self.assertEquals(root.get('sub.z'), "z value")

    def testFileDelete(self):
        path = os.path.join(os.path.dirname(__file__), "simple.coil")
        root = parser.Parser(["sub: { @file: %s ~y.z}" % repr(path)]).root()
        self.assertEquals(root.get('sub.x'), "x value")
        self.assert_(root.get('sub.y', None) is not None)
        self.assertRaises(KeyError, lambda: root.get('sub.y.z'))

    def testFileExpansion(self):
        path = os.path.join(os.path.dirname(__file__), "simple.coil")
        text = "path: %s sub: { @file: '${@root.path}' }" % repr(path)
        root = parser.Parser([text]).root()
        self.assertEquals(root.get('sub.x'), "x value")
        self.assertEquals(root.get('sub.y.z'), "z value")

    def testPackage(self):
        root = parser.Parser(["@package: 'coil.test:simple.coil'"]).root()
        self.assertEquals(root.get('x'), "x value")
        self.assertEquals(root.get('y.z'), "z value")

    def testComments(self):
        root = parser.Parser(["y: [12 #hello\n]"]).root()
        self.assertEquals(root.get("y"), [12])

    def testParseError(self):
        for coil in (
            "struct: {",
            "struct: }",
            "a: b:",
            ":",
            "[]",
            "a: ~b",
            "@x: 2",
            "x: 12c",
            "x: 12.c3",
            "a: 1 x: .a",
            "x: @root",
            "x: ..a",
            'x: {@package: "coil.test:nosuchfile"}',
            # should get internal parse error
            'x: {@package: "coil.test:test_parser.py"}',
            'z: [{x: 2}]', # can't have struct in list
            r'z: "lalalal \"', # string is not closed
            'a: 1 z: [ =@root.a ]',
            'a: {@extends: @root.b}', # b doesn't exist
            'a: {@extends: ..b}', # b doesn't exist
            'a: {@extends: x}',
            'a: {@extends: .}',
            'a: [1 2 3]]',
            ):
            self.assertRaises(errors.CoilError, parser.Parser, [coil])

    def testOrder(self):
        self.assertEqual(parser.Parser(["x: =y y: 'foo'"]).root()['x'], "foo")
        self.assertEqual(parser.Parser(["y: 'foo' x: =y"]).root()['x'], "foo")

    def testList(self):
        root = parser.Parser(["x: ['a' 1 2.0 True False None]"]).root()
        self.assertEqual(root['x'], ['a', 1, 2.0, True, False, None])

    def testNestedList(self):
        root = parser.Parser(["x: ['a' ['b' 'c']]"]).root()
        self.assertEqual(root['x'], ['a', ['b', 'c']])

class ExtendsTestCase(unittest.TestCase):

    def setUp(self):
        self.text = """
            A: {
                a: "a"
                b: "b"
                c: "c"
            }
            B: {
                @extends: ..A
                e: [ "one" 2 "omg three" ]
                ~c
            }
            C: {
                a: ..A.a
                b: @root.B.b
            }
            D: {
                @extends: @root.B
            }
            """
        self.tree = parser.Parser(self.text.splitlines()).root()

    def testBasic(self):
        self.assertEquals(self.tree['A']['a'], "a")
        self.assertEquals(self.tree['A']['b'], "b")
        self.assertEquals(self.tree['A']['c'], "c")
        self.assertEquals(len(self.tree['A']), 3)

    def testExtendsAndDelete(self):
        self.assertEquals(self.tree['B']['a'], "a")
        self.assertEquals(self.tree['B']['b'], "b")
        self.assertRaises(KeyError, lambda: self.tree['B']['c'])
        self.assertEquals(self.tree['B']['e'], [ "one", 2, "omg three" ])
        self.assertEquals(len(self.tree['B']), 3)

    def testRefrences(self):
        self.assertEquals(self.tree['C']['a'], "a")
        self.assertEquals(self.tree['C']['b'], "b")
        self.assertEquals(len(self.tree['C']), 2)

    def testExtends(self):
        self.assertEquals(self.tree['D']['a'], "a")
        self.assertEquals(self.tree['D']['b'], "b")
        self.assertRaises(KeyError, lambda: self.tree['D']['c'])
        self.assertEquals(self.tree['D']['e'], [ "one", 2, "omg three" ])
        self.assertEquals(len(self.tree['D']), 3)

class ParseFileTestCase(unittest.TestCase):

    def setUp(self):
        self.path = os.path.dirname(__file__)

    def testExample(self):
        root = parse_file(os.path.join(self.path, "example.coil"))
        self.assertEquals(root['x'], 1)
        self.assertEquals(root.get('y.a'), 2)
        self.assertEquals(root.get('y.x'), 1)
        self.assertEquals(root.get('y.a2'), 2)

    def testExample2(self):
        root = parse_file(os.path.join(self.path, "example2.coil"))
        self.assertEquals(root.get('sub.x'), "foo")
        self.assertEquals(root.get('sub.y.a'), "bar")
        self.assertEquals(root.get('sub.y.x'), "foo")
        self.assertEquals(root.get('sub.y.a2'), "bar")
        self.assertEquals(root.get('sub2.y.a'), 2)
        self.assertEquals(root.get('sub2.y.x'), 1)
        self.assertEquals(root.get('sub2.y.a2'), 2)

    def testExample3(self):
        root = parse_file(os.path.join(self.path, "example3.coil"))
        self.assertEquals(root['x'], 1)
        self.assertEquals(root.get('y.a'), 2)
        self.assertEquals(root.get('y.x'), 1)
        self.assertEquals(root.get('y.a2'), 2)
        self.assertEquals(root.get('y.b'), 3)

