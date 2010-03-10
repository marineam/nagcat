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

"""Oracle Queries"""

import re

from zope.interface import classProvides
from twisted.internet import threads
from twisted.enterprise import adbapi

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None

from nagcat import errors, log, query


class _DBColumn:
    """describes the name and type of a column, to facilitate mapping the
    attributes of a DB column into XML attribs (taken by processing
    the contents of a cx_Oracle.Cursor.description)"""

    # taken from http://cx-oracle.sourceforge.net/html/cursor.html
    CX_VAR_COLUMNS = ('name', 'type', 'display_size', 'internal_size',
                     'precision', 'scale', 'null_ok')

    def __init__(self, desc):
        """Take the decription of a cx_Oracle variable, and make it an actual
        object"""

        # these are the attributes that this item will contain
        for k,v in zip(self.CX_VAR_COLUMNS, desc):
            setattr(self, k, v)
    def __str__(self):
        return "<_DBColumn %s:%s>" % (self.name, self.type)
    def __repr__(self):
        return str(self)


class _OracleConnectionPool(adbapi.ConnectionPool):
    """a specialized connectionPool, with a modified _runQuery that fires with
    the variables of the cursor as well as the the result"""

    #! this makes me twitch, but I can't think of a better way to get the list of
    #! variables out of the otherwise inaccessible cursor
    def _runQuery(self, cursor, *args, **kwargs):
        """Override the adbpapi.ConnectionPool._runQuery, to remember and return
        the cursor, as well as the resulting data"""

        # the parent-class _runQuery() returns the result of cursor.fetchall(),
        # which might be dangerous if a rogue query were to return a huge dataset.
        result = adbapi.ConnectionPool._runQuery(self, cursor, *args, **kwargs)
        columns = map(lambda c: _DBColumn(c), cursor.description)
        return (columns, result)


class OracleSQL(query.Query):
    """Use oracle sql to execute a query against one of the databases via
    twisted's adbapi"""

    classProvides(query.IQuery)

    name = "oraclesql"

    # the field of the configuration struct that we care about
    CONF_FIELDS = ['user', 'password', 'dsn', 'sql', 'binds']

    def __init__(self, conf):
        if not etree or not cx_Oracle:
            raise errors.InitError(
                    "cx_Oracle and lxml are required for Oracle support.")

        super(OracleSQL, self).__init__(conf)
        # need to make this take a tnsname system instead of just a DBI
        for fieldname in self.CONF_FIELDS:
            if fieldname in conf:
                self.conf[fieldname] = conf.get(fieldname)

    def _start(self):
        self.dbpool = _OracleConnectionPool('cx_Oracle', user=self.conf['user'],
                                          password=self.conf['password'],
                                          dsn=self.conf['dsn'],
                                          threaded=True,
                                          cp_reconnect=True)
        log.debug("running sql %s", self.conf['sql'])
        self.deferred = self.dbpool.runQuery(self.conf['sql'],
                                             self.conf.get('binds', {}))
        self.deferred.addCallback(self._success)
        self.deferred.addErrback(self._failure_oracle)
        return self.deferred

    def _success(self, result):
        """success receives a (columns, data) pair, where 'columns' is a list of
        _DBColumns and 'data' is the actual data returned from the query.
        Convert it to XML and return it
        """
        columns, table = result
        tree = _result_as_xml(columns, table)
        self.result = etree.tostring(tree, pretty_print=False)
        log.debug("OracleSQL success: %s rows returned", len(table))
        self._cleanup()
        return self.result

    @errors.callback
    def _failure_oracle(self, result):
        """Catch common oracle failures here"""
        log.debug("Fail! %s", result.value)
        # cleanup now, since we mightn't be back
        self._cleanup()
        raise_oracle_warning(result)

    def _cleanup(self):
        """Closes the ConnectionPool"""
        self.dbpool.close()


class OraclePLSQL(query.Query):
    """A query that uses cx_oracle directly (allowing for stored procedure calls)
    results (via "out" parameters) are returned in XML
    """

    classProvides(query.IQuery)

    name = "oracle_plsql"

    # fields we expect to see in the conf
    CONF_FIELDS = ['user', 'password', 'dsn', 'procedure', 'parameters', 'DBI']

    # these are the orderings for the parameters in the config. I would have
    # preferred to specify the parameters as dicts, but coil apparently does not
    # support that yet.
    IN_PARAMETER_FIELDS = ['direction', 'name', 'value']
    OUT_PARAMETER_FIELDS = ['direction', 'name', 'type']

    def __init__(self, conf):
        if not etree or not cx_Oracle:
            raise errors.InitError(
                "cx_Oracle and lxml are required for Oracle support.")
        super(OraclePLSQL, self).__init__(conf)
        for fieldname in self.CONF_FIELDS:
            if fieldname in conf:
                self.conf[fieldname] = conf.get(fieldname)

        self.check_config(conf)

        # setup the DBI, if we don't have it
        if "DBI" not in self.conf:
            self.conf['DBI'] = "%s/%s@%s" % (
                self.conf['user'], self.conf['password'], self.conf['dsn'])

        # data members to be filled in later
        self.connection = None
        self.parameters = None
        self.cursor = None


    def check_config(self, conf):
        """check the config for semantic errors"""

        if not ('user' in self.conf and 'password' in self.conf
                and 'dsn' in self.conf) and not 'DBI' in self.conf:
            raise errors.ConfigError(conf,
                "needs values for user, password, dsn or for DBI")

        if 'procedure' not in self.conf:
            raise errors.ConfigError(conf, "needs a 'procedure' name to call")

        # check the format of the parameters list.
        for param in self.conf['parameters']:
            if not isinstance(param, list):
                raise errors.ConfigError(conf, '%s should be a list of lists'
                                        % self.conf['parameters'])

            if len(param) != 3 or not param[0] in ['out', 'in']:
                msg = ("%s should be a list of three elements: "
                       "[ <in|out> <param_name> <type|value>" % param)
                raise errors.ConfigError(conf, msg)


    def buildparam(self, p):
        """Parameters in the conf are in list form. Convert them to dicts (including
        suitable DB variables where relevant) for easier sending/receiving"""

        def makeDBtype(s):
            "convert to the name of a cx_Oracle type, using the much-dreaded eval()"
            try:
                return eval('cx_Oracle.' + s.upper())
            except AttributeError as err:
                raise TypeError("'%s' is not a recognized Oracle type" % s)

        if p[0].lower() == 'in':
            retval = dict(zip(self.IN_PARAMETER_FIELDS, p))
            retval['db_val'] = retval['value']
            return retval
        elif p[0].lower() == 'out':
            retval = dict(zip(self.OUT_PARAMETER_FIELDS, p))
            retval['db_val'] = self.cursor.var(makeDBtype(retval['type']))
            return retval
        else:
            raise errors.InitError(
                "Unrecognized direction '%s' in %s (expected 'in' or 'out')" % (p[0], p))


    def _start(self):
        log.debug("running procedure")

        ## Should do some connection pooling here...
        self.connection = cx_Oracle.Connection(self.conf['DBI'], threaded=True)
        self.cursor = self.connection.cursor()

        self.parameters = [self.buildparam(p) for p in self.conf['parameters']]
        # result is a modified copy of self.parameters

        #result = self.callproc(self.conf['query.procedure'], self.parameters)
        db_params = [p['db_val']  for p in self.parameters]
        self.deferred = threads.deferToThread(self.cursor.callproc,
                                              self.conf['procedure'],
                                              db_params)
        self.deferred.addCallback(self._success)
        self.deferred.addErrback(self._failure_oracle)
        return self.deferred

    @errors.callback
    def _failure_oracle(self, result):
        log.debug("Fail! %s", result.value)
        self._cleanup()
        raise_oracle_warning(result)

    def _cleanup(self):
        """Closes the DB connection"""
        self.connection.close()

    def _success(self, result):
        """Callback for the deferred that handles the procedure call"""
        self.result = self._outparams_as_xml(result)
        self._cleanup()
        return self.result

    def _outparams_as_xml(self, result_set):
        """Convert the 'out' parameters into XML. """

        def only_out_params(resultset):
            """(too big for a lambda) only convert those parameters that were
            direction='out', along with their matching definitions from the conf"""
            return [p for p in zip(self.parameters, result_set)
                    if p[0]['direction'] == 'out']
        try:
            root = etree.Element('result')
            for param, db_value in only_out_params(result_set):
                if not isinstance(db_value, cx_Oracle.Cursor):
                    # for non-cursor results, all is treated as text
                    tree = etree.Element(param['name'], type="STRING")
                    if db_value: tree.text = str(db_value)
                else:
                    # for cursors, we will convert to tables
                    columns = map(_DBColumn, db_value.description)
                    table = db_value.fetchall()
                    tree = _result_as_xml(columns, table, param['name'])
                root.append(tree)
            return etree.tostring(root, pretty_print=False)

        except Exception as err:
            raise errors.TestCritical("XML conversion error!: %s" % err)


def _result_as_xml(columns, result_table, name="queryresult"):
        """Convert an executed query into XML, using the columns to get the
        names and types of the column tags"""

        # example query: select 1 as foo from dual
        # returns: '<queryresult><row><foo type="NUMBER">1</foo></row></queryresult>'
        try:
            tree = etree.Element(name)
            for row in result_table:
                xmlrow = etree.Element('row')
                for col, val in zip(columns, row):
                    xmlrow.append(_xml_element(col, val))
                tree.append(xmlrow)
            return tree
        except Exception as err:
            raise errors.TestCritical("XML conversion error!: %s" % err)


def _xml_element(col, value):
        name = re.sub("[^\w]","", col.name.lower())
        elt = etree.Element(name, type=col.type.__name__)
        if value != None:
            elt.text = str(value)
        return elt


def raise_oracle_warning(failure):
    """A handy wrapper for handling cx_Oracle failures in Query objects"""

    if isinstance(failure.value, cx_Oracle.Warning):
        # Exception raised for important warnings and defined by the DB API
        # but not actually used by cx_Oracle.
        raise errors.TestWarning(failure.value)

    if isinstance(failure.value, cx_Oracle.InterfaceError):
        # Exception raised for errors that are related to the database
        # interface rather than the database itself. It is a subclass of
        # Error.
        raise errors.TestCritical(failure.value)

    if isinstance(failure.value, cx_Oracle.DatabaseError):
        # Exception raised for errors that are related to the database. It
        # is a subclass of Error.
        raise errors.TestCritical(failure.value)

    if isinstance(failure.value, cx_Oracle.Error):
        # Exception that is the base class of all other exceptions
        # defined by cx_Oracle and is a subclass of the Python
        # StandardError exception (defined in the module exceptions).
        raise errors.TestCritical(failure.value)

    log.debug("Unhandled failure! %s", failure)
