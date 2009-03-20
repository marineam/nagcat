"""Tests for coil.struct."""

import unittest
from coil import struct, errors

class BasicTestCase(unittest.TestCase):

    def setUp(self):
        # Use a tuple to preserve order
        self.data = (('first', {
                        'string': "something",
                        'float': 2.5,
                        'int': 1 }),
                    ('second', "something else"),
                    ('last', [ "list", "of", "strings" ]))
        self.struct = struct.Struct(self.data)

    def testFirstLevelContains(self):
        for key in ('first', 'second', 'last'):
            self.assert_(key in self.struct)

    def testSecondLevelContains(self):
        for key in ('string', 'float', 'int'):
            self.assert_(key in self.struct['first'])

    def testKeyOrder(self):
        self.assertEquals(self.struct.keys(), ['first', 'second', 'last'])

    def testGetItem(self):
        self.assertEquals(self.struct['second'], "something else")

    def testGetSimple(self):
        self.assertEquals(self.struct.get('second'), "something else")

    def testGetDefault(self):
        self.assertEquals(self.struct.get('bogus', "awesome"), "awesome")

    def testGetPath(self):
        self.assertEquals(self.struct.get('first.int'), 1)

    def testGetParent(self):
        child = self.struct['first']
        self.assertEquals(child.get('..second'), "something else")

    def testGetRoot(self):
        child = self.struct['first']
        self.assertEquals(child.get('@root.second'), "something else")

    def testIterItems(self):
        itemlist = [("one", 1), ("two", 2), ("three", 3)]
        self.assertEquals(list(struct.Struct(itemlist).iteritems()), itemlist)

    def testKeyMissing(self):
        self.assertRaises(errors.KeyMissingError, lambda: self.struct['bogus'])
        self.assertRaises(errors.KeyMissingError, self.struct.get, 'bad')

    def testKeyType(self):
        self.assertRaises(errors.KeyTypeError, lambda: self.struct[None])
        self.assertRaises(errors.KeyTypeError, self.struct.get, None)

    def testKeyValue(self):
        self.assertRaises(errors.KeyValueError,
                self.struct.set, 'first#', '')
        self.assertRaises(errors.KeyValueError,
                self.struct.set, 'first..second', '')

    def testDict(self):
        self.assertEquals(self.struct['first'].dict(), dict(self.data[0][1]))

    def testSetShort(self):
        s = struct.Struct()
        s['new'] = True
        self.assertEquals(s['new'], True)

    def testSetLong(self):
        s = struct.Struct()
        s['new.sub'] = True
        self.assertEquals(s['new.sub'], True)
        self.assertEquals(s['new']['sub'], True)

class ExpansionTestCase(unittest.TestCase):

    def testExpand(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}"
        root.expand()
        self.assertEquals(root.get('bar'), "omgwtfbbq")

    def testExpandItem(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}"
        self.assertEquals(root.get('bar'), "omgwtf${foo}")
        self.assertEquals(root.expanditem('bar'), "omgwtfbbq")

    def testExpandDefault(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}${baz}"
        root.expand({'foo':"123",'baz':"456"})
        self.assertEquals(root.get('bar'), "omgwtfbbq456")

    def testExpandItemDefault(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}${baz}"
        self.assertEquals(root.get('bar'), "omgwtf${foo}${baz}")
        self.assertEquals(root.expanditem('bar',
            defaults={'foo':"123",'baz':"456"}), "omgwtfbbq456")

    def testExpandIgnore(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}${baz}"
        root.expand(ignore=True)
        self.assertEquals(root.get('bar'), "omgwtfbbq${baz}")
        root.expand(ignore=('baz',))
        self.assertEquals(root.get('bar'), "omgwtfbbq${baz}")

    def testExpandItemIgnore(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = "omgwtf${foo}${baz}"
        self.assertEquals(root.get('bar'), "omgwtf${foo}${baz}")
        self.assertEquals(root.expanditem('bar', ignore=('baz',)),
                "omgwtfbbq${baz}")

    def testExpandError(self):
        root = struct.Struct()
        root["bar"] = "omgwtf${foo}"
        self.assertRaises(KeyError, root.expand)
        self.assertEquals(root.get('bar'), "omgwtf${foo}")

    def testExpandItemError(self):
        root = struct.Struct()
        root["bar"] = "omgwtf${foo}"
        self.assertEquals(root.get('bar'), "omgwtf${foo}")
        self.assertRaises(KeyError, root.expanditem, 'bar')
        self.assertEquals(root.get('bar'), "omgwtf${foo}")

    def testExpandInList(self):
        root = struct.Struct()
        root["foo"] = "bbq"
        root["bar"] = [ "omgwtf${foo}" ]
        self.assertEquals(root['bar'][0], "omgwtf${foo}")
        root.expand()
        self.assertEquals(root['bar'][0], "omgwtfbbq")

    def testExpandMixed(self):
        root = struct.Struct()
        root["foo"] = "${bar}"
        self.assertEquals(root.expanditem("foo", {'bar': "a"}), "a")
        root["bar"] = "b"
        self.assertEquals(root.expanditem("foo", {'bar': "a"}), "b")

