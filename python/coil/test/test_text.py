"""Test text format."""

import os
import unittest
from twisted.python.util import sibpath
from coil import text, struct


class TextTestCase(unittest.TestCase):

    def testStringParse(self):
        for structStr, value in (
            [r'x: "\n\r \t\""', u'\n\r \t\"'],
            [r'x: "hello"', u"hello"],
            [r'x: "\\n"', ur"\n"],
            ['x: "' + u"\u3456".encode("utf-8") + '"', u'\u3456'],
            [r'x: "\" \ x"', u'" \ x'],
            ):
            x = text.fromString(structStr).get("x")
            self.assertEquals(x, value)
            self.assert_(isinstance(x, unicode))

    def testIntParse(self):
        for structStr, value in [
            ('x: 1', 1),
            ('x: 20909', 20909),
            ('x: -34324', -34324),
            ('x: 0', 0)]:
            x = text.fromString(structStr).get("x")
            self.assertEquals(x, value)

    def testListParse(self):
        for s, l in [#('x: [None 1 2.3 ["hello \\"world"] [7]]',
                     # [None, 1, 2.3, [u'hello "world'], [7]]),
                     ('x: ["a" "b"]', [u"a", u"b"])]:
            self.assertEquals(text.fromString(s).get("x"), l)

    def testComments(self):
        s = "y: [12 #hello\n]"
        self.assertEquals(text.fromString(s).get("y"), [12])

    def testStruct(self):
        s = '''
struct: {
    x: 12  y: 14
    substruct: {
        a: "hello world"
        b: False
    }
}
a-number: 2
-moo: 3
'''
        root = text.fromString(s)
        self.assertEquals(list(root.attributes()), ["struct", "a-number", "-moo"])
        self.assertEquals(root.get("a-number"), 2)
        self.assertEquals(root.get("-moo"), 3)
        struct_ = root.get("struct")
        self.assertEquals(list(struct_.attributes()), ["x", "y", "substruct"])
        self.assertEquals(struct_.get("x"), 12)
        substruct = struct_.get("substruct")
        self.assertEquals(list(substruct.attributes()), ["a", "b"])
        self.assertEquals(substruct.get("b"), False)

    def testAttributePath(self):
        s = '''
struct: {
    sub: {a: 1}
    sub.b: 2
    sub.c: 3
    sub.d-e: 5
}'''
        root = text.fromString(s).get("struct")
        self.assertEquals(root.get("sub").get("a"), 1)
        self.assertEquals(root.get("sub").get("b"), 2)
        self.assertEquals(root.get("sub").get("c"), 3)
        self.assertEquals(root.get("sub").get("d-e"), 5)
    
    def testBad(self):
        for s in [
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
            'x: {@file: "%s"}' % (sibpath(__file__, "nosuchfile"),),
            'x: {@package: "coil.test:test_text.py"}', # should get internal parse error
            'z: [{x: 2}]', # can't have struct in list
            r'z: "lalalal \"', # string is not closed
            'a: 1 z: [ =@root.a ]',
            'a: {@extends: @root.b}', # b doesn't exist
            'a: {@extends: ..b}', # b doesn't exist
            'a: {@extends: x}',
            'a: {@extends: .}',
            'a: [1 2 3]]',
            ]:
            self.assertRaises(text.ParseError, text.fromString, s)

        try:
            text.fromString("x: 1\n2\n")
        except text.ParseError, e:
            self.assertEquals(e.line, 2)
            self.assertEquals(e.column, 1)
        else:
            raise RuntimeError

    def testDeleted(self):
        s = '''
struct1: {
    a: {b: 1 x: 3}
    c: 2
    d: {b: 2}
}
struct2: {
    @extends: ..struct1
    ~c
    ~a.b
}
~struct2.d
'''
        root = text.fromString(s).get("struct2")
        self.assertEquals(list(root.attributes()), ["a"])
        self.assertEquals(list(root.get("a").attributes()), ["x"])
        self.assert_(not root.has_key("d"))
        self.assert_(not root.has_key("c"))
    
    def testLink(self):
        s = '''
struct: {
    sub: {a: =..b c2: =c c: 1}
    b: 2
    c: =@root.x
}
x: "hello"
'''
        root = struct.StructNode(text.fromString(s))
        self.assertEquals(root.struct.c, "hello")
        self.assertEquals(root.struct.sub.a, 2)
        self.assertEquals(root.struct.sub.c2, 1)

    def testSimpleExtends(self):
        s = '''
bar: {
   a: 1
   b: 2
   c: {d: 7}
}

foo: {
   @extends: ..bar
   a: 3
   c: {
       @extends: @root.bar.c
       b2: =...bar.b
       e: 4
   }
   c.f: 9 # nicer way of doing it
}
'''
        foo = struct.StructNode(text.fromString(s)).foo
        self.assertEquals(foo.a, 3)
        self.assertEquals(foo.b, 2)
        self.assertEquals(foo.c.d, 7)
        self.assertEquals(foo.c.b2, 2)
        self.assertEquals(foo.c.e, 4)
        self.assertEquals(foo.c.f, 9)
        for n in ("a", "b", "c"):
            self.assert_(foo.has_key(n))
        for n in ("d", "b2", "e", "f"):
            self.assert_(foo.c.has_key(n))
    
    def testStupidExtensionSemantics(self):
        s = '''
            base: {x: 1}
            sub: {
              @extends: ..base
            }
            base.y: 2 # sub should NOT have y
            '''
        s = text.fromString(s)
        self.assertEquals(s.get("base").get("y"), 2)
        self.assertEquals(s.get("sub").get("x"), 1)
        self.assertRaises(struct.StructAttributeError, lambda: s.get("sub").get("y"))        
        self.assert_(not s.get("sub").has_key("y"))
    
    def _testFile(self, root):
        self.assertEquals(root.get("x"), 1)
        self.assertEquals(root.get("y").get("a"), 2)
    
    def testPathImport(self):
        path = os.path.abspath(sibpath(__file__, "example.coil"))
        s = 'x: {@file: "%s"}' % path
        self._testFile(text.fromString(s).get("x"))
        s = 'x: {@file: "example.coil"}'
        self._testFile(text.fromString(s, __file__).get("x"))
    
    def testPackageImport(self):
        s = 'x: {@package: "coil:test/example.coil"}'
        self._testFile(text.fromString(s).get("x"))
        s = 'x: {@package: "coil.test:example.coil"}'
        self._testFile(text.fromString(s).get("x"))

    def testFileImport(self):
        path = sibpath(__file__, "example2.coil")
        s = text.fromFile(path)
        node = struct.StructNode(s)
        # make sure relative and absolute paths work and are relative
        # to sub-struct that did the @file.
        self.assertEquals(node.sub.y.x, u"foo")
        self.assertEquals(node.sub.y.a2, u"bar")
        self.assertEquals(node.sub2.y.a2, 2) # 'a' didn't get overriden this time
        # XXX TODO
        #self.assertEquals(node.sub3.a2, 2) # 'a' didn't get overriden this time
        
    def testFileSubImport(self):
        # @file can reference a sub-struct of imported file.
        s = text.fromFile(sibpath(__file__, "filesubimport.coil"))
        node = struct.StructNode(s)
        # 0. Top-level import:
        self.assertEquals(node.imp.sub.x, "default")
        self.assertEquals(node.imp.sub.y, 2)
        self.assertEquals(node.imp.sub.two.parentx, "default")
        # 1. Single level sub-struct:
        self.assertEquals(node.sub.x, "foo")
        self.assertEquals(node.sub.y, 2)
        self.assertEquals(node.sub.two.parentx, "foo")
        # 2. Two level sub-struct:
        self.assertEquals(node.subsub.parentx, "bar")
        self.assertEquals(node.subsub.value, "hello")
    
    def testFileImportAtTopLevel(self):
        path = sibpath(__file__, "example3.coil")
        s = text.fromFile(path)
        node = struct.StructNode(s)
        self.assertEquals(node.y.a, 2)
        self.assertEquals(node.y.b, 3)
        self.assertEquals(node.x, 1)

    def testRootLinks(self):
        s = """x: 1
               y: {x: =@root.x}
               z: {y2: {@extends: ...y}}"""
        node = struct.StructNode(text.fromString(s))
        self.assertEquals(node.x, 1)
        self.assertEquals(node.y.x, 1)
        self.assertEquals(node.z.y2.x, 1)
