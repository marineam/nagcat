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

class Link(tokenizer.Location):
    """A temporary symbolic link to another item"""

    def __init__(self, path, container, location=None):
        """
        @param path: A path or the original Token defining the path.
        @type path: L{tokenizer.Token} or str
        @param container: The parent L{Struct} object.
        @type container: L{Struct}
        @param location: Description of where the link is defined.
        @type location L{str}
        """

        assert isinstance(container, Struct)
        assert isinstance(path, basestring)
        tokenizer.Location.__init__(self, location)
        self.path = path

class Struct(tokenizer.Location, DictMixin):
    """A dict-like object for use in trees."""

    KEY = re.compile(r'^%s$' % tokenizer.Tokenizer.KEY_REGEX)
    PATH = re.compile(r'^%s$' % tokenizer.Tokenizer.PATH_REGEX)
    EXPAND = re.compile(r'\$\{(%s)\}' % tokenizer.Tokenizer.PATH_REGEX)

    #: Signal L{Struct.get} to raise an error if key is not found
    _raise = object()
    #: Signal L{Struct._set} to preserve location data for key
    _keep = object()

    # These first methods likely would need to be overridden by subclasses

    def __init__(self, base=(), container=None, name=None,
            recursive=True, location=None):
        """
        @param base: A C{dict} or C{Struct} to initilize this one with.
        @param container: the parent C{Struct} if there is one.
        @param name: The name of this C{Struct} in C{container}.
        @param recursive: Recursively convert all mapping objects in
            C{base} to C{Struct} objects.
        @param location: The where this C{Struct} is defined.
        """

        assert isinstance(container, Struct) or container is None
        assert isinstance(base, (list, tuple, dict, DictMixin))

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
            if recursive and isinstance(value, (dict, DictMixin)):
                value = self.__class__(value, self, key)
            self[key] = value

    def get(self, path, default=_raise, expand=False, ignore=False):
        """Get a value from any Struct in the tree.

        @param path: key or arbitrary path to fetch.
        @param default: return this value if item is missing.
            Note that the behavior here differs from a C{dict}. If
            C{default} is unspecified and missing a L{KeyMissingError}
            will be raised as __getitem__ does, not return C{None}.
        @param expand: Set to True or a mapping object (dict or
            Struct) to enable string variable expansion (ie ${var}
            values are expanded). If a mapping object is given it
            will be used for checked for values not found in C{Struct}.
            Set to False to disable all expansion.
        @param ignore: Set to True (to ignore all) or a list of names
            that are allowed to be missing during expansion.
            If expansion is enabled and a key is not found and also
            not ignored then a L{KeyMissingError} is raised.

        @return: The fetched item or the value of C{default}.
        """

        parent, key = self._get_path_parent(path)

        if parent is self:
            try:
                value = self._values[key]
            except KeyError:
                if default == self._raise:
                    raise errors.KeyMissingError(self, key)
                else:
                    value = default

            value = self._expand_item(key, value, expand, ignore)
        else:
            value = parent.get(key, default, expand, ignore)

        return value

    def _set(self, path, value, location=None):
        """Set a value in any Struct in the tree.

        @param path: key or arbitrary path to set.
        @param value: value to save.
        @param location: defines where this option was defined.
            Set to L{Struct._keep} to not modify the location if it
            is already set, this is used by L{Struct.expand}.
        """

        parent, key = self._get_path_parent(path, True)

        if parent is self:
            if not re.match(self.KEY, key):
                raise errors.KeyValueError(self, key)

            if isinstance(value, Struct) and not value.container:
                value.container = self
                value.name = key

            if key not in self:
                self._order.append(key)

            self._values[key] = value
        else:
            parent._set(key, value, location)

    def __delitem__(self, path):
        parent, key = self._get_path_parent(path)

        if parent is self:
            if not re.match(self.KEY, key):
                raise errors.KeyValueError(self, key)

            try:
                self._order.remove(key)
            except ValueError:
                raise errors.KeyMissingError(self, key)

            try:
                del self._values[key]
            except KeyError:
                raise errors.KeyMissingError(self, key)
        else:
            del parent[key]

    def __contains__(self, key):
        return key in self._values

    def __iter__(self):
        """Iterate over the ordered list of keys."""
        for key in self._order:
            yield key

    # The remaining methods likely do not need to be overridden in subclasses

    def __getitem__(self, path):
        return self.get(path)

    def __setitem__(self, path, value):
        return self._set(path, value)

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

    def expand(self, expand=True, ignore=False, recursive=False):
        """Expand all Links and string variable substitutions.

        This is useful when disabling expansion during parsing,
        adding some extra values to the tree, then expanding.
        """

        if expand is False or expand is None:
            return

        for key in self:
            value = self.get(key, expand=expand, ignore=ignore)
            if recursive and isinstance(value, Struct):
                value.expand(expand, ignore, True)
            else:
                self._set(key, value, self._keep)

    def copy(self):
        """Recursively copy this C{Struct}"""

        return self.__class__(self)

    def dict(self):
        """Recursively copy this C{Struct} into normal dict objects"""

        new = {}
        for key, value in self.iteritems():
            if value and isinstance(value, Struct):
                value = value.dict()
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

    def _get_path_parent(self, path, add_parents=False):
        """Returns the second to last Struct and last key in the path.

        If add_parents is true then create parent Structs as needed.
        """

        # TODO: This function (and its users) should probably be recursive.

        if not isinstance(path, basestring):
            raise errors.KeyTypeError(self, path)

        split = path.split('.')
        lastkey = split.pop()
        struct = self

        if not re.match(self.KEY, lastkey) or not re.match(self.PATH, path):
            raise errors.KeyValueError(self, path)

        # Relative path's start with .. which adds one extra blank string 
        if split and not split[0]:
            del split[0]

        # Walk the path if there is one
        for key in split:
            if key == '@root':
                while struct.container:
                    struct = struct.container
                    assert isinstance(struct, Struct)
            elif not key:
                struct = struct.container
                if struct is None:
                    raise errors.CoilStructError(self,
                            "reference past tree root: %s" % path)
                assert isinstance(struct, Struct)
            else:
                try:
                    struct = struct[key]
                except KeyError:
                    if add_parents:
                        new = struct.__class__()
                        struct[key] = new
                        struct = new
                    else:
                        raise errors.KeyMissingError(self, key, path)

                if not isinstance(struct, Struct):
                    raise errors.CoilStructError(self,
                            "key %s in path %s is not a Struct"
                            % (repr(key), repr(path)))

        return struct, lastkey

    def _expand_item(self, key, orig, expand, ignore):
        """Expand Links and all ${var} values inside a string.
        
        @param key: Name of item we are expanding
        @param orig: Value of the item
        @param expand: Extra mapping object to use for expansion values
            if expand is None or False then this function is a no-op.
        @param ignore: True or a list of variables to ignore if missing,
            otherwise raise L{KeyMissingError}
        """

        # TODO: catch all circular references!

        def expand_one(match):
            name = match.group(1)

            if name == key:
                raise errors.CoilStructError(self,
                        "A path inside %s is itself" % name)
            try:
                value = self.get(name, expand=expand, ignore=ignore)
            except errors.KeyMissingError, ex:
                if expand is not True and name in expand:
                    value = expand[name]
                elif ignore is True or ignore and name in ignore:
                    value = match.group(0)
                else:
                    #ex.location(
                    raise ex

            if isinstance(value, (Struct, list)):
                raise errors.CoilStructError(self,
                        "Attempted to expand %s of type %s in item %s"
                        % (name, type(value), key))
            elif not isinstance(value, basestring):
                return str(value)
            else:
                return value

        if expand is None or expand is False:
            return orig

        if isinstance(orig, Link):
            if key == orig.path:
                raise errors.CoilStructError(self,
                        "Item %s is a link that points to itself" % key)
            try:
                value = self.get(orig.path, expand=expand, ignore=ignore)
            except KeyError, ex:
                if expand is not True and value.path in expand:
                    value = expand[orig.path]
                elif ignore is True or ignore and orig.path in ignore:
                    pass
                else:
                    #ex.location(
                    raise
        elif isinstance(orig, basestring):
            value = self.EXPAND.sub(expand_one, orig)
        elif isinstance(orig, list):
            value = []
            for item in orig:
                value.append(self._expand_item(key, item, expand, ignore))
        else:
            value = orig

        return value

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
