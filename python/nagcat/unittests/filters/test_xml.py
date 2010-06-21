# Copyright 2009-2010 ITA Software, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from lxml import etree
from twisted.trial import unittest
from nagcat import errors, filters

class XPathTestCase(unittest.TestCase):

    example = """
    <html>
        <head>
            <title>Test XML</title>
        </head>
        <body>
            <div class="title">This has been a test</div>
            <p>Text #1</p><p>Text #2</p>
        </body>
    </html>
    """

    def testBasic(self):
        f = filters.Filter(object(), "xpath://div/text()")
        self.assertEquals(f.filter(self.example), "This has been a test")

    def testMissing(self):
        f = filters.Filter(object(), "xpath://span/text()")
        self.assertIsInstance(f.filter(self.example), errors.Failure)

    def testDefault(self):
        f = filters.Filter(object(), "xpath[none]://span/text()")
        self.assertEquals(f.filter(self.example), "none")

    def testBad(self):
        f = filters.Filter(object(), "xpath://span/text()")
        self.assertIsInstance(f.filter("<foo></bar>"), errors.Failure)

    def testXML(self):
        f = filters.Filter(object(), "xpath://title")
        self.assertEquals(f.filter(self.example), "<title>Test XML</title>")

    def testMultiXML(self):
        f = filters.Filter(object(), "xpath://p")
        self.assertEquals(f.filter(self.example),
                "<p>Text #1</p>\n<p>Text #2</p>")

class XSLTTestCase(unittest.TestCase):

    # example swiped from wikipedia
    raw_xml = """<?xml version="1.0"?>
        <persons>
          <person username="JS1">
            <name>John</name>
            <family-name>Smith</family-name>
          </person>
          <person username="MI1">
            <name>Morka</name>
            <family-name>Ismincius</family-name>
          </person>
        </persons>
    """

    raw_xslt = """<?xml version="1.0"?>
        <xsl:stylesheet
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                version="1.0">
          <xsl:output method="xml" indent="yes"/>

          <xsl:template match="/persons">
            <root>
              <xsl:apply-templates select="person"/>
            </root>
          </xsl:template>

          <xsl:template match="person">
            <name username="{@username}">
              <xsl:value-of select="name" />
            </name>
          </xsl:template>

        </xsl:stylesheet>
    """

    result = ('<root>\n'
              '  <name username="JS1">John</name>\n'
              '  <name username="MI1">Morka</name>\n'
              '</root>\n')

    def testBasic(self):
        f = filters.Filter(object(), "xslt:%s" % self.raw_xslt)
        self.assertEquals(str(f.filter(self.raw_xml)), self.result)

    def testPath(self):
        path = os.path.abspath(self.mktemp())
        fd = open(path, "w")
        fd.write(self.raw_xslt)
        fd.close()

        f = filters.Filter(object(), "xslt:%s" % path)
        self.assertEquals(str(f.filter(self.raw_xml)), self.result)

    def testBadXSLTXML(self):
        self.assertRaises(errors.InitError,
                filters.Filter, object(), "xslt:blah")

    def testBadXSLT(self):
        self.assertRaises(errors.InitError,
                filters.Filter, object(), "xslt:<blah></blah>")

    def testBadInputXML(self):
        f = filters.Filter(object(), "xslt:%s" % self.raw_xslt)
        self.assertIsInstance(f.filter("blah"), errors.Failure)

class HTMLTestCase(unittest.TestCase):

    example = """
    <html>
        <head>
            <title>Test HTML</title>
        </head>
        <body>
            <div class="title">This has been a test</div>
            <p>Text #1<p>Text #2</p>
        </body>
    </html>
    """

    expect = """
    <html>
        <head>
            <title>Test HTML</title>
        </head>
        <body>
            <div class="title">This has been a test</div>
            <p>Text #1</p><p>Text #2</p>
        </body>
    </html>
    """

    def testBasic(self):
        f = filters.Filter(object(), "html")
        xml = f.filter(self.example)
        self.assertIsInstance(xml, str)
        self.assertEqualsXML(xml, self.expect)

    def assertEqualsXML(self, result, expect):
        # Parse the xml, strip white space, and convert back
        # this allows us to compare if they are logically equal
        parser = etree.XMLParser(remove_blank_text=True)
        result = etree.tostring(etree.XML(result, parser))
        expect = etree.tostring(etree.XML(expect, parser))
        self.assertEquals(result, expect)
