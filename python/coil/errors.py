# Copyright (c) 2008-2009 ITA Software, Inc.
# See LICENSE.txt for details.

class CoilError(Exception):
    """Generic error for Coil"""

    def __init__(self, location, reason):
        self.reason = reason
        self.location(location)
        Exception.__init__(self, reason)

    def location(self, location):
        """Update the parser location for this exception.
        This is useful for properly tagging L{StructError}s that are
        raised during parse time.
        """

        self.filePath = location.filePath
        self.line = location.line
        self.column = location.column

    def __str__(self):
        if self.filePath or self.line:
            return "<%s:%s> %s" % (self.filePath, self.line, self.reason)
        else:
            return self.reason

class StructError(CoilError):
    """Generic error for L{Struct} objects, used by various Key errors"""

    def __init__(self, struct, reason):
        self.structPath = struct.path()
        CoilError.__init__(self, struct, reason)

    def __str__(self):
        if self.filePath or self.line:
            return "<%s %s:%s> %s" % (self.structPath,
                    self.filePath, self.line, self.reason)
        else:
            return "<%s> %s" % (self.structPath, self.reason)

class KeyMissingError(StructError, KeyError):
    """The given key was not found"""

    def __init__(self, struct, key):
        msg = "The key %s was not found" % repr(key)
        self.key = key
        StructError.__init__(self, struct, msg)

class KeyTypeError(StructError, TypeError):
    """The given key was not a string"""

    def __init__(self, struct, key):
        msg = "Keys must be strings, got %s" % type(key)
        StructError.__init__(self, struct, msg)

class KeyValueError(StructError, ValueError):
    """The given key contained invalid characters"""

    def __init__(self, struct, key):
        msg = "The key %s contains invalid characters" % repr(key)
        StructError.__init__(self, struct, msg)

class ValueTypeError(StructError):
    """The given item in a path was not the correct type"""

    def __init__(self, struct, key, item_type, need_type):
        msg = "the item at %s is a %s, expected %s" % (
                repr(key), item_type.__name__, need_type.__name__)
        StructError.__init__(self, struct, msg)

class CoilParseError(CoilError):
    """General error during parsing"""
    pass

class CoilUnicodeError(CoilParseError):
    """Invalid unicode string"""
    pass
