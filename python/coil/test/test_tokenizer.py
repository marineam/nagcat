"""Tests for coil.tokenizer."""

import unittest
from coil import tokenizer

class TokenizerTestCase(unittest.TestCase):

    def testEmpty(self):
        tok = tokenizer.Tokenizer([""])
        self.assertEquals(tok.next().type, 'EOF')

    def testPath(self):
        tok = tokenizer.Tokenizer(["somekey"])
        first = tok.next()
        self.assert_(isinstance(first, tokenizer.Token))
        self.assertEquals(first.type, 'PATH')
        self.assertEquals(first.value, "somekey")
        self.assertEquals(first.line, 1)
        self.assertEquals(first.column, 1)
        self.assertEquals(tok.next().type, 'EOF')

    def testString(self):
        tok = tokenizer.Tokenizer(["'string'"])
        first = tok.next()
        self.assertEquals(first.type, 'VALUE')
        self.assert_(isinstance(first.value, str))
        self.assertEquals(first.value, "string")
        self.assertEquals(first.line, 1)
        self.assertEquals(first.column, 1)
        self.assertEquals(tok.next().type, 'EOF')

    def testUnocide(self):
        tok = tokenizer.Tokenizer(
                [u"'\u3456'".encode("utf-8")],
                encoding='utf-8')
        first = tok.next()
        self.assertEquals(first.type, 'VALUE')
        self.assert_(isinstance(first.value, unicode))
        self.assertEquals(first.value, u"\u3456")
        self.assertEquals(first.line, 1)
        self.assertEquals(first.column, 1)
        self.assertEquals(tok.next().type, 'EOF')

    def testNumbers(self):
        tok = tokenizer.Tokenizer(["1 2.0 -3 -4.0 0"])
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, 1)
        self.assert_(isinstance(token.value, int))
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, 2.0)
        self.assert_(isinstance(token.value, float))
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, -3)
        self.assert_(isinstance(token.value, int))
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, -4)
        self.assert_(isinstance(token.value, float))
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, 0)
        self.assert_(isinstance(token.value, int))
        self.assertEquals(tok.next().type, 'EOF')

    def testBoolean(self):
        tok = tokenizer.Tokenizer(["True False"])
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, True)
        self.assert_(isinstance(token.value, bool))
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, False)
        self.assert_(isinstance(token.value, bool))
        self.assertEquals(tok.next().type, 'EOF')

    def testNone(self):
        tok = tokenizer.Tokenizer(["None"])
        token = tok.next()
        self.assertEquals(token.type, 'VALUE')
        self.assertEquals(token.value, None)
        self.assertEquals(tok.next().type, 'EOF')

    def testCounters(self):
        tok = tokenizer.Tokenizer(["'string' '''foo''' '' '''''' other",
                                   "'''multi line string",
                                   "it is crazy''' hi",
                                   "  bye"])
        tok.next()
        token = tok.next()
        self.assertEquals(token.line, 1)
        self.assertEquals(token.column, 10)
        token = tok.next()
        self.assertEquals(token.line, 1)
        self.assertEquals(token.column, 20)
        token = tok.next()
        self.assertEquals(token.line, 1)
        self.assertEquals(token.column, 23)
        token = tok.next() # other
        self.assertEquals(token.line, 1)
        self.assertEquals(token.column, 30)
        token = tok.next()
        self.assertEquals(token.line, 2)
        self.assertEquals(token.column, 1)
        token = tok.next() # hi
        self.assertEquals(token.line, 3)
        self.assertEquals(token.column, 16)
        token = tok.next() # bye
        self.assertEquals(token.line, 4)
        self.assertEquals(token.column, 3)
        self.assertEquals(tok.next().type, 'EOF')

    def testSpecialChars(self):
        tok = tokenizer.Tokenizer(["{}[]:~="])
        self.assertEquals(tok.next().type, '{')
        self.assertEquals(tok.next().type, '}')
        self.assertEquals(tok.next().type, '[')
        self.assertEquals(tok.next().type, ']')
        self.assertEquals(tok.next().type, ':')
        self.assertEquals(tok.next().type, '~')
        self.assertEquals(tok.next().type, '=')
        self.assertEquals(tok.next().type, 'EOF')
