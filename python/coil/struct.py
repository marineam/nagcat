# Copyright (c) 2005-2006 Itamar Shtull-Trauring.
# Copyright (c) 2008-2009 ITA Software, Inc.
# See LICENSE.txt for details.

"""Struct is the core object in Coil.

Struct objects are similar to dicts except they are intended to be used
as a tree and can handle relative references between them.
"""

from __future__ import generators

import re
from UserDict import DictMixin

from coil import tokenizer, errors

class Link(object):
    """A temporary symbolic link to another item"""

    def __init__(self, path):
        """
        @param path: A path to point at.
        @type path: string
        """
        self.path = path

class Struct(tokenizer.Location, DictMixin):
    """A dict-like object for use in trees."""

    KEY = re.compile(r'^%s$' % tokenizer.Tokenizer.KEY_REGEX)
    PATH = re.compile(r'^%s$' % tokenizer.Tokenizer.PATH_REGEX)
    EXPAND = re.compile(r'\$\{(%s)\}' % tokenizer.Tokenizer.PATH_REGEX)

    #: Signal L{Struct.get} to raise an error if key is not found
    _raise = object()
    #: Signal L{Struct.set} to preserve location data for key
    _keep = object()

    # These first methods likely would need to be overridden by subclasses

    def __init__(self, base=(), container=None, name=None, location=None):
        """
        @param base: A L{dict}, L{Struct}, or a list of (key, value)
            tuples to initialize with. Any child C{dict} or C{Struct}
            will be recursively copied as a new child C{Struct}
            If order is important a list of key, value tuples may also
        @param container: the parent C{Struct} if there is one.
        @param name: The name of this C{Struct} in C{container}.
        @param location: The where this C{Struct} is defined.
            This is normally only used by the L{Parser}.
        """

        assert isinstance(base, (list, tuple, dict, Struct))

        tokenizer.Location.__init__(self, location)
        self.container = container
        self.name = name
        self._values = {}
        self._order = []

        if isinstance(base, (list, tuple)):
            base_iter = iter(base)
        else:
            base_iter = base.iteritems()

        for key, value in base_iter:
            if isinstance(value, (Struct, dict)):
                value = self.__class__(value)
            elif isinstance(value, list):
                value = list(value)
            self[key] = value

    def _get(self, key):
        return self._values[key]

    def _set(self, key, value):
        self._values[key] = value
        if key not in self._order:
            self._order.append(key)

    def _del(self, key):
        del self._values[key]
        try:
            self._order.remove(key)
        except ValueError:
            raise KeyError

    def __contains__(self, key):
        return key in self._values

    def __iter__(self):
        """Iterate over the ordered list of keys."""
        for key in self._order:
            yield key

    # The remaining methods likely do not need to be overridden in subclasses

    def __getitem__(self, path):
        return self.get(path)

    def get(self, path, default=_raise):
        """Get a value from any Struct in the tree.

        @param path: key or arbitrary path to fetch.
        @param default: return this value if item is missing.
            Note that the behavior here differs from a C{dict}. If
            C{default} is unspecified and missing a L{KeyMissingError}
            will be raised as __getitem__ does, not return C{None}.

        @return: The fetched item or the value of C{default}.
        """

        parent, key = self._get_next_parent(path)

        if parent is self:
            if not key:
                value = self
            else:
                try:
                    value = self._get(key)
                except KeyError:
                    if default is self._raise:
                        raise errors.KeyMissingError(self, key)
                    else:
                        value = default
        else:
            value = parent.get(key, default)

        return value

    def __setitem__(self, path, value):
        return self.set(path, value)

    def set(self, path, value, location=None):
        """Set a value in any Struct in the tree.

        @param path: key or arbitrary path to set.
        @param value: value to save.
        @param location: defines where this value was defined.
            Set to L{Struct._keep} to not modify the location if it
            is already set, this is used by L{Struct.expanditem}.
        """

        parent, key = self._get_next_parent(path, True)

        if parent is self:
            if not key or not self.KEY.match(key):
                raise errors.KeyValueError(self, key)

            if isinstance(value, Struct) and not value.container:
                value.container = self
                value.name = key

            self._set(key, value)
        else:
            parent.set(key, value, location)

    def __delitem__(self, path):
        parent, key = self._get_next_parent(path)

        if parent is self:
            if not key:
                raise errors.KeyValueError(path)

            try:
                self._del(path)
            except KeyError:
                raise errors.KeyMissingError(self, key)
        else:
            del parent[key]

    def keys(self):
        """Get an ordered list of keys."""
        return list(iter(self))

    def attributes(self):
        """Alias for C{keys()}.

        Only for compatibility with Coil <= 0.2.2.
        """
        return self.keys()

    def has_key(self, key):
        """True if key is in this C{Struct}"""
        return key in self

    def iteritems(self):
        """Iterate over the ordered list of (key, value) pairs."""
        for key in self:
            yield key, self[key]

    def expand(self, defaults=(), ignore=(), recursive=True, block=()):
        """Expand all L{Link}s and string variable substitutions in
        this and all child L{Struct}s. Useful when expansion must be
        or partially ignored during parse-time and then finished later.

        This modifies the tree!

        @param defaults: default values to use if undefined.
        @type defaults: dict
        @param ignore: a set of keys that are ignored if undefined
            and not in defaults. Otherwise raise L{KeyMissingError}.
        @type ignore: any container
        @param recursive: recursively expand sub-structs
        @type recursive: bool
        @param block: a set of absolute paths that cannot be expanded.
            This is used internally to avoid circular references.
        @type block: any container
        """

        abspath = self.path()
        if abspath in block:
            raise errors.StructError(self, "Circular reference to %s" % abspath)

        block = list(block)
        block.append(abspath)

        for key in self:
            value = self.expanditem(key, defaults, ignore, block)
            self.set(key, value, self._keep)
            if recursive and isinstance(value, Struct):
                value.expand(defaults, ignore, True, block)

    def expanditem(self, path, defaults=(), ignore=(), block=()):
        """Expand L{Link}s and string variable substitutions in an item.

        This does not make any changes to the tree.
        
        @param defaults: default values to use if undefined.
        @type defaults: dict
        @param ignore: a set of keys that are ignored if undefined
            and not in defaults. If simply set to True then all
            are ignored. Otherwise raise L{KeyMissingError}.
        @type ignore: True any container
        @param block: a set of absolute paths that cannot be expanded.
            This is used internally to avoid circular references.
        @type block: any container
        """

        def expand_substr(match):
            subkey = match.group(1)
            try:
                subval = self.expanditem(subkey, defaults, ignore, block)
            except errors.KeyMissingError, ex:
                if ex.key in defaults:
                    subval = defaults[ex.key]
                elif ignore is True or ex.key in ignore:
                    subval = match.group(0)
                else:
                    raise

            return str(subval)

        def expand_link(link):
            try:
                subval = self.expanditem(link.path, defaults, ignore, block)
            except errors.KeyMissingError, ex:
                if ex.key in defaults:
                    subval = defaults[ex.key]
                elif ignore is True or ex.key in ignore:
                    subval = match.group(0)
                else:
                    raise

            # Structs and lists must be copied
            if isinstance(subval, Struct):
                subval = self.__class__(subval)
            if isinstance(subval, list):
                subval = list(subval)

            return subval

        # defaults should only contain simple keys, not paths.
        for key in defaults:
            assert "." not in key

        parent, key = self._get_next_parent(path)

        if parent is self:
            abspath = self.path()
            if key:
                abspath = "%s.%s" % (self.path(), key)
            if abspath in block:
                raise errors.StructError(self,
                        "Circular reference to %s" % abspath)

            block = list(block)
            block.append(abspath)

            value = self.get(key)

            if isinstance(value, basestring):
                value = self.EXPAND.sub(expand_substr, value)
            elif isinstance(value, Link):
                value = expand_link(value)
            elif isinstance(value, list):
                for i in xrange(len(value)):
                    if isinstance(value[i], basestring):
                        value[i] = self.EXPAND.sub(expand_substr, value[i])

            return value
        else:
            return parent.expanditem(key, defaults, ignore, block)

    def copy(self):
        """Recursively copy this C{Struct}"""

        return self.__class__(self)

    def dict(self):
        """Recursively copy this C{Struct} into normal dict objects"""

        new = {}
        for key, value in self.iteritems():
            if isinstance(value, Struct):
                value = value.dict()
            elif isinstance(value, dict):
                value = value.copy()
            elif isinstance(value, list):
                value = list(value)
            new[key] = value

        return new

    def path(self):
        """Get the absolute path of this C{Struct} in the tree"""

        if not self.container:
            return "@root"
        else:
            return "%s.%s" % (self.container.path(), self.name)

    def __str__(self):
        attrs = []
        for key, val in self.iteritems():
            if isinstance(val, Struct):
                attrs.append("%s: %s" % (repr(key), str(val)))
            else:
                attrs.append("%s: %s" % (repr(key), repr(val)))
        return "{%s}" % " ".join(attrs)

    def __repr__(self):
        attrs = ["%s: %s" % (repr(key), repr(val))
                 for key, val in self.iteritems()]
        return "%s({%s})" % (self.__class__.__name__, ", ".join(attrs))

    def _get_next_parent(self, path, add_parents=False):
        """Returns the next Struct in a path and the remaining path.

        If the path is a single key just return self and the key.
        If add_parents is true then create parent Structs as needed.
        """

        if not isinstance(path, basestring):
            raise errors.KeyTypeError(self, path)

        if path.startswith("@root"):
            if self.container:
                parent = self.container
            else:
                parent = self
                path = path[5:]
        elif path.startswith(".."):
            if self.container:
                parent = self.container
            else:
                raise errors.StructError(self, "Reference past root")
            path = path[1:]
        elif path.startswith("."):
            parent = self
            path = path[1:]
        elif "." not in path:
            parent = self
        else:
            # check for mid-path parent references
            if ".." in path:
                raise errors.KeyValueError(self, path)

            split = path.split(".", 1)
            key = split.pop(0)
            if split:
                path = split[0]
            else:
                path = ""

            try:
                parent = self.get(key)
            except errors.KeyMissingError:
                if add_parents:
                    parent = self.__class__()
                    self.set(key, parent)
                else:
                    raise

            if not isinstance(parent, Struct):
                raise errors.ValueTypeError(self, key, type(parent), Struct)

        if parent is self and "." in path:
            # Great, we went nowhere but there is still somewhere to go
            parent, path = self._get_next_parent(path, add_parents)

        return parent, path


#: For compatibility with Coil <= 0.2.2, use C{KeyError} or L{KeyMissingError}
StructAttributeError = errors.KeyMissingError

class StructNode(object):
    """For compatibility with Coil <= 0.2.2, use L{Struct} instead."""

    def __init__(self, struct, container=None):
        # The container argument is now bogus,
        # just make sure it matches the struct.
        assert isinstance(struct, Struct)
        assert container is None or container == struct.container
        self._struct = struct
        self._container = struct.container

    def has_key(self, attr):
        return self._struct.has_key(attr)

    def get(self, attr, default=Struct._raise):
        val = self._struct.get(attr, default)
        if isinstance(val, Struct):
            val = self.__class__(val)
        return val

    def attributes(self):
        return self._struct.keys()

    def iteritems(self):
        for item in self._struct.iteritems():
            yield item

    def __getattr__(self, attr):
        return self.get(attr)
