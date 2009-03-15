# Copyright (c) 2005-2006 Itamar Shtull-Trauring.
# Copyright (c) 2008-2009 ITA Software, Inc.
# See LICENSE.txt for details.

"""Compatibility with <= 0.2.2, do not use in new code!"""

from coil import parser, parse_file, errors

ParseError = errors.CoilError

def fromSequence(iterOfStrings, filePath=None):
    """Load a Struct from a sequence of strings.

    @param filePath: path the strings were loaded from. Required for
    relative @file arguments to work.
    """
    # The strings in 0.2.2 were allowed to contain newlines. We now
    # expect the iter to be of lines, not arbitrary strings.
    lines = []
    for line in iterOfStrings:
        lines += line.splitlines()
    return parser.Parser(lines, filePath, 'utf-8').root()

def fromString(st, filePath=None):
    """Load a Struct from a string.

    @param filePath: path the string was loaded from. Required for
    relative @file arguments to work.
    """
    return parser.Parser(st.splitlines(), filePath, 'utf-8').root()

def fromFile(path):
    """Load a struct from a file, given a path on the filesystem."""
    return parse_file(path)
