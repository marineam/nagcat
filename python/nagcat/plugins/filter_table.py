# Copyright 2008-2010 ITA Software, Inc.
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

"""Table (csv, etc) Filter"""

import csv
from cStringIO import StringIO
from zope.interface import classProvides
from nagcat import errors, filters, log

class TableFilter(filters._Filter):
    """Select data out of CSV and similarly formatted data"""

    classProvides(filters.IFilter)

    name = "table"

    def __init__(self, test, default, arguments):
        super(TableFilter, self).__init__(test, default, arguments)

        args = self.arguments.split(',', 1)
        if args[0] and args[0].isdigit():
            self.row = int(args[0])
        elif args[0]:
            self.row = args[0]
        else:
            self.row = None

        if len(args) == 2 and args[1]:
            if args[1].isdigit():
                self.col = int(args[1])
            else:
                self.col = args[1]
        else:
            self.col = None

        if self.row is None and self.col is None:
            raise errors.InitError("Empty table filter: %r" % self.arguments)

    @errors.callback
    def filter(self, result):
        try:
            return self._filter_without_default(result)
        except errors.TestCritical:
            if self.default is not None:
                return self.default
            else:
                raise

    def _filter_without_default(self, result):
        log.debug("Fetching cell %s,%s from table", self.row, self.col)

        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(result)
            reader = csv.reader(StringIO(result), dialect)
            table = list(reader)
        except csv.Error, ex:
            raise errors.TestCritical("Failed to parse table: %s" % ex)

        if not table:
            raise errors.TestCritical("Empty table")

        # If col is not an index, assume we have a header to work with.
        if isinstance(self.col, str):
            try:
                col = table[0].index(self.col)
            except ValueError:
                raise errors.TestCritical("No such column %s" % self.col)
        else:
            col = self.col

        if self.row is not None:
            if isinstance(self.row, int):
                try:
                    row = table[self.row]
                except IndexError:
                    raise errors.TestCritical(
                            "No such row %s, last row is %s" %
                            (self.row, len(table)-1))
            else:
                row = None
                for r in table:
                    if r and r[0] == self.row:
                        row = r
                        break

                if row is None:
                    raise errors.TestCritical(
                            "No row starting with %s" % (self.row,))

            if col is not None:
                try:
                    return row[col]
                except IndexError:
                    raise errors.TestCritical("No such column %s in row %s" %
                            (self.col, self.row))
            else:
                table = [row]
        else:
            data = []
            for i, row in enumerate(table):
                try:
                    data.append([row[col]])
                except IndexError:
                    raise errors.TestCritical("No such column %s in row %s" %
                            (self.col, i))
            table = data

        # Our result was a row or a column rather than cell so re-output
        io = StringIO()
        writer = csv.writer(io, dialect, lineterminator='\n')
        writer.writerows(table)
        return io.getvalue().rstrip()
