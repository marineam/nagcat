# Copyright 2010 ITA Software, Inc.
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
#
# cython: profile=True
# cython: infer_types=False

"""Python parser for nagios object files"""

from nagcat import errors

# libc string functions for parsing
cdef extern from "string.h":
    char *strsep(char **stringp, char *delim)
    long strspn(char *s, char *accept)
    long strcspn(char *s, char *reject)
    long strlen(char *s)
    int strcmp(char *s1, char *s2)

cdef inline void _ignore(char **ptr):
    """eat whitespace and comments"""
    # ptr[0] == *ptr; ptr[0][0] == **ptr

    # position becomes NULL at EOF
    if not ptr[0]:
        return

    while True:
        # strip whitepsace
        ptr[0] += strspn(ptr[0], " \t\n")

        # strip comments
        if ptr[0][0] == '#' or ptr[0][0] == ';':
            ptr[0] += strcspn(ptr[0], "\n")
        else:
            return

cdef inline char* _strend(char *haystack, char *needle):
    """Similar to strstr but checks if haystack ends with needle.
    (It doesn't actually search for any needle like strstr does though)

    The return value is the address of needle within haystack or NULL.
    """
    cdef char* addr = haystack + strlen(haystack) - strlen(needle)

    if addr < haystack:
        return NULL
    elif strcmp(addr, needle) == 0:
        return addr
    else:
        return NULL

class ParseError(errors.InitError):
    """Error while parsing a nagios object file"""

cdef class ObjectParser:
    """Parse a given config file for the requested objects.

    Note that this expects files generated *by* Nagios
    such objects.cache or status.dat
    """

    # Cython >= 0.12 uses the 3.x style bytes type for its
    # raw byte string instead of the 2.x style str type.
    cdef dict _objects
    cdef bytes  _buffer
    cdef char *_pos

    def __init__(self, object_file, object_types=(), object_select=()):
        self._objects = {}

        try:
            fd = open(object_file)
            self._buffer = <bytes>fd.read()
            self._pos = self._buffer
            fd.close()
        except IOError, ex:
            raise ParseError("Failed to read Nagios object file: %s" % ex)

        self._parse()
        self._pos = NULL
        self._buffer = None

    cdef int _parse(self) except -1:
        while self._pos:
            self._parse_object()

    cdef int _parse_object(self) except -1:
        cdef char *tok, *delim, *tmp
        cdef str objtype, attr
        cdef dict objdata = {}

        _ignore(&self._pos)

        tok = strsep(&self._pos, " \t")
        if not tok or not strlen(tok):
            return 0

        if strcmp(tok, "define") == 0:
            tok = strsep(&self._pos, " \t")
            if not tok:
                raise ParseError("Unexpected end of input.")
            objtype = tok
            delim = " \t"
        else:
            # If tok ends with status strip it off
            tmp = _strend(tok, "status")
            if tmp:
                tmp[0] = '\0'
            objtype = tok
            delim = "="

        tok = strsep(&self._pos, " \t\n")
        if not tok:
            raise ParseError("Unexpected end of input.")
        if strcmp(tok, "{") != 0:
            raise ParseError("Unexpected token: %s" % tok)

        while True:
            _ignore(&self._pos)

            if self._pos[0] == '}':
                self._pos += 1
                break

            tok = strsep(&self._pos, delim)
            if not tok:
                raise ParseError("Unexpected end of input.")

            name = tok
            tok = strsep(&self._pos, "\n")
            if not tok:
                raise ParseError("Unexpected end of input.")

            # successfully got data!
            objdata[name] = tok

        if objtype in self._objects:
            self._objects[objtype].append(objdata)
        else:
            self._objects[objtype] = [objdata]

        return 0

    def __getitem__(self, key):
        return self._objects[key]

    def __contains__(self, key):
        return key in self._objects

    def types(self):
        return self._objects.keys()
