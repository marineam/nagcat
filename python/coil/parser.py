# Copyright (c) 2008-2009 ITA Software, Inc.
# See LICENSE.txt for details.

"""Coil Parser"""

import os
import sys

from coil import tokenizer, struct, errors

class StructPrototype(struct.Struct):
    """A temporary struct used for parsing only.

    This Struct tracks links and inheritance so they can be processed
    when parsing is all done. This is important because it allows us
    to do fancy things with inheritance and catch errors during
    parse-time rather than run-time.
    """

    def __init__(self, base=(), container=None, name=None):
        struct.Struct.__init__(self, base, container, name)

        # Secondary items are ones that are inherited via @extends or @file
        # They must be tracked separately so we can raise errors on
        # double adds and deletes in the primary values.
        self._secondary_values = {}
        self._secondary_order = []
        # _deleted is a list of items that exist in one of the parents
        # but have been removed from this Struct by ~foo tokens.
        self._deleted = []

    def get(self, path, default=struct.Struct._raise,
            expand=False, ignore=False):
        parent, key = self._get_path_parent(path)

        if parent is self:
            try:
                return struct.Struct.get(self, key, self._raise,
                        expand=expand, ignore=ignore)
            except KeyError:
                value = self._secondary_values.get(key, self._raise)

                if value is not self._raise:
                    return self._expand_item(key, value, expand, ignore)
                elif default is not self._raise:
                    return default
                else:
                    raise
        else:
            return parent.get(key, default, expand, ignore)

    def _set(self, path, value, location=None):
        parent, key = self._get_path_parent(path)

        if parent is self:
            self._validate_doubleset(key)

            if path in self._secondary_values:
                del self._secondary_values[key]

            struct.Struct._set(self, key, value, location)
        else:
            parent._set(key, value, location)

    def __delitem__(self, path):
        parent, key = self._get_path_parent(path)

        if parent is self:
            self._validate_doubleset(key)

            try:
                struct.Struct.__delitem__(self, key)
            except KeyError:
                if path in self._secondary_values:
                    del self._secondary_values[key]
                    self._secondary_order.remove(key)
                else:
                    raise

            self._deleted.append(key)
        else:
            del parent[key]

    def __contains__(self, key):
        return key in self._values or key in self._secondary_values

    def __iter__(self):
        for key in self._secondary_order:
            yield key
        for key in self._order:
            yield key

    def extends(self, base, relative=False):
        """Add a struct as another parent.

        @param base: A Struct or dict to extend.
        @param relative: Convert @root links to relative links.
            Used when extending a Struct from another file.
        """

        for key, value in base.iteritems():
            if key in self or key in self._deleted:
                continue

            # Copy child Structs so that they can be edited independently
            if isinstance(value, struct.Struct):
                new = self.__class__(container=self, name=key)
                new.extends(value, relative)
                value = new

            # Convert absolute to relative links if required
            if (relative and isinstance(value, struct.Link) and
                    value.path.startswith("@root")):
                path = ""
                container = base
                while container.container:
                    container = container.container
                    path += "."
                path += value.path[5:]
                value.path = path

            self._secondary_values[key] = value
            self._secondary_order.append(key)

    def _validate_doubleset(self, key):
        """Private: check that key has not been used (excluding parents)"""

        if key in self._deleted or key in self._values:
            raise errors.CoilStructError(self,
                    "Setting/deleting '%s' twice" % repr(key))


class Parser(object):
    """The standard coil parser"""

    def __init__(self, input_, path=None, encoding=None,
            expand=True, ignore=False):
        """
        @param input_: An iterator over lines of input.
            Typically a C{file} object or list of strings.
        @param path: Path to input file, used for errors and @file imports.
        @param encoding: Read strings using the given encoding. All
            string values will be C{unicode} objects rather than C{str}.
        @param expand: Set to True or a mapping object (dict or
            Struct) to enable string variable expansion (ie ${var}
            values are expanded). If a mapping object is given it
            will be checked for the value before this C{Struct}.
            Set to False to disable all expansion.
        @param ignore: Set to True (to ignore all) or a list of names
            that are allowed to be missing during expansion.
            If expansion is enabled and a key is not found and also
            not ignored then a L{KeyMissingError} is raised.
        """

        if path:
            self._path = os.path.abspath(path)
        else:
            self._path = None

        self._encoding = encoding
        self._tokenizer = tokenizer.Tokenizer(input_, self._path, encoding)

        # Create the root Struct and parse!
        self._prototype = StructPrototype()

        while self._tokenizer.peek('~', 'PATH', 'EOF').type != 'EOF':
            self._parse_attribute(self._prototype)

        self._tokenizer.next('EOF')
        self._root = struct.Struct(self._prototype)
        self._root.expand(expand, ignore, True)

    def root(self):
        """Get the root Struct"""
        return self._root

    def prototype(self):
        """Get the raw unexpanded prototype, you probably don't want this."""
        return self._prototype

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._root)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self._root)

    def _parse_attribute(self, container):
        """name: value"""

        token = self._tokenizer.next('~', 'PATH')

        if token.type == '~':
            token = self._tokenizer.next('PATH')

            try:
                del container[token.value]
            except errors.CoilStructError, ex:
                ex.location(token)
                raise ex
        else:
            self._tokenizer.next(':')

            if token.value[0] == '@':
                special = getattr(self, "_special_%s" % token.value[1:], None)
                if special is None:
                    raise errors.CoilParseError(token,
                            "Unknown special attribute: %s" % token.value)
                else:
                    special(container)
            else:
                self._parse_value(container, token.value)

    def _parse_value(self, container, name):
        """path, number, or string"""

        token = self._tokenizer.peek('{', '[', '=', 'PATH', 'VALUE')

        if token.type == '{':
            # Got a struct, will be added inside _parse_struct
            self._parse_struct(container, name)
        elif token.type == '[':
            # Got a list, will be added inside _parse_list
            self._parse_list(container, name)
        elif token.type == '=':
            # Got a reference, chomp the =, save the link
            self._tokenizer.next('=')
            self._parse_link(container, name)
        elif token.type == 'PATH':
            # Got a reference, save the link
            self._parse_link(container, name)
        else:
            # Plain old boring values
            self._parse_plain(container, name)

    def _parse_struct(self, container, name):
        """{ attrbute... }"""

        token = self._tokenizer.next('{')

        try:
            new = StructPrototype()
            container[name] = new
        except errors.CoilStructError, ex:
            ex.location(token)
            raise ex

        while self._tokenizer.peek('~', 'PATH', '}').type != '}':
            self._parse_attribute(new)

        self._tokenizer.next('}')

    def _parse_list(self, container, name):
        """[ number or string ... ]"""

        token = self._tokenizer.next('[')

        new = list()
        container[name] = new

        while self._tokenizer.peek(']', 'VALUE').type != ']':
            item = self._tokenizer.next('VALUE')
            new.append(item.value)

        self._tokenizer.next(']')

    def _parse_link(self, container, name):
        """some.path"""

        token = self._tokenizer.next('PATH')
        link = struct.Link(token.value)
        container._set(name, link, location=token)

    def _parse_plain(self, container, name):
        """number, string, bool, or None"""

        token = self._tokenizer.next('VALUE')
        container._set(name, token.value, location=token)

    def _special_extends(self, container):
        """Handle @extends: some.struct"""

        token = self._tokenizer.next('PATH')

        try:
            parent = container.get(token.value)
        except errors.CoilStructError, ex:
            ex.location(token)
            raise ex

        container.extends(parent)

    def _extend_with_file(self, container, file_path, struct_path):
        """Parse another coil file and merge it into the tree"""

        coil_file = open(file_path)
        parent = self.__class__(coil_file, file_path,
                self._encoding).prototype()

        if struct_path:
            parent = parent.get(struct_path)

        container.extends(parent, True)

    def _special_file(self, container):
        """Handle @file"""

        token = self._tokenizer.next('[', 'VALUE')

        if token.type == '[':
            # @file: [ "file_name" "substruct_name" ]
            file_path = self._tokenizer.next('VALUE').value
            struct_path = self._tokenizer.next('VALUE').value
            self._tokenizer.next(']')
        else:
            # @file: "file_name"
            file_path = token.value
            struct_path = ""

        if (not isinstance(file_path, basestring) or
                not isinstance(struct_path, basestring)):
            raise errors.CoilParseError(token, "@file value must be a string")

        if self._path and not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(self._path), file_path)

        if not os.path.isabs(file_path):
            raise errors.CoilParseError(token,
                    "Unable to find absolute path: %s" % file_path)

        try:
            self._extend_with_file(container, file_path, struct_path)
        except IOError, ex:
            raise errors.CoilParseError(token, str(ex))

    def _special_package(self, container):
        """Handle @package"""

        token = self._tokenizer.next('VALUE')

        if not isinstance(token.value, basestring):
            raise errors.CoilParseError(token,
                    "@package value must be a string")

        try:
            package, path = token.value.split(":", 1)
        except ValueError:
            errors.CoilParseError(token,
                    '@package value must be "package:path"')

        parts = package.split(".")
        parts.append("__init__.py")

        fullpath = None
        for directory in sys.path:
            if not isinstance(directory, basestring):
                continue
            if os.path.exists(os.path.join(directory, *parts)):
                fullpath = os.path.join(directory, *(parts[:-1] + [path]))
                break

        if not fullpath:
            raise errors.CoilParseError(token,
                    "Unable to find package: %s" % package)

        try:
            self._extend_with_file(container, fullpath, "")
        except IOError, ex:
            raise errors.CoilParseError(token, str(ex))
