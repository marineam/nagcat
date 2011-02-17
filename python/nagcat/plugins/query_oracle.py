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

import os
import re
import signal
import cPickle

from zope.interface import classProvides
from twisted.internet import defer, error, process, protocol, reactor
from twisted.python import failure
from coil.struct import Struct

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None

from nagcat import errors, log, query


class PickleReader(protocol.ProcessProtocol):

    def __init__(self, fd):
        self.fd = fd
        self.data = ""
        self.timedout = False
        self.deferred = defer.Deferred()

    def childDataReceived(self, fd, data):
        assert self.fd == fd
        self.data += data

    def timeout(self):
        self.timedout = True
        if self.transport.pid:
            try:
                os.kill(self.transport.pid, signal.SIGTERM)
            except OSError, ex:
                log.warn("Failed to send TERM to a subprocess: %s", ex)

    def processEnded(self, reason):
        if isinstance(reason.value, error.ProcessDone):
            try:
                self.deferred.callback(cPickle.loads(self.data))
            except Exception:
                self.deferred.errback(failure.Failure())
        elif (isinstance(reason.value, error.ProcessTerminated)
                and self.timedout):
            self.deferred.errback(errors.Failure(errors.TestCritical(
                    "Timeout waiting for Oracle query to finish.")))
        else:
            self.deferred.errback(reason)


class ForkIt(process.Process):

    def __init__(self, timeout, func, *args, **kwargs):
        readfd, writefd = os.pipe()
        self._write = os.fdopen(writefd, 'w')
        self._func = func
        self._args = args
        self._kwargs = kwargs
        proto = PickleReader(writefd)

        # Setup timeout
        call_id = reactor.callLater(timeout, proto.timeout)
        proto.deferred.addBoth(self._cancelTimeout, call_id)

        # Setup shutdown cleanup
        call_id = reactor.addSystemEventTrigger(
                'after', 'shutdown', proto.timeout)
        proto.deferred.addBoth(self._cancelCleanup, call_id)

        process.Process.__init__(self, reactor, executable=None, args=None,
                environment=None, path=None, proto=proto,
                childFDs={0:0, 1:1, 2:2, writefd: writefd})
        self.pipes[writefd] = self.processReaderFactory(
                reactor, self, writefd, readfd)
        self._write.close()

    def getResult(self):
        return self.proto.deferred

    def _cancelTimeout(self, result, call_id):
        if call_id.active():
            call_id.cancel()
        return result

    def _cancelCleanup(self, result, call_id):
        reactor.removeSystemEventTrigger(call_id)
        return result

    def _execChild(self, *ignore, **kgnore):
        """Run our function instead of exec"""
        try:
            result = self._func(*self._args, **self._kwargs)
        except Exception:
            result = failure.Failure()
        cPickle.dump(result, self._write, -1)
        self._write.close()
        os._exit(0)

    def _resetSignalDisposition(self):
        """Reset non-standard signal handlers."""
        for signalnum in xrange(1, signal.NSIG):
            if signal.getsignal(signalnum) not in (None,
                    signal.SIG_DFL, signal.SIG_IGN):
                signal.signal(signalnum, signal.SIG_DFL)


class _DBColumn:
    """describes the name and type of a column, to facilitate mapping the
    attributes of a DB column into XML attribs (taken by processing
    the contents of a cx_Oracle.Cursor.description)"""

    # taken from http://cx-oracle.sourceforge.net/html/cursor.html
    CX_VAR_COLUMNS = ('name', 'type', 'display_size', 'internal_size',
                     'precision', 'scale', 'null_ok')

    # used for ensuring the xml is sane
    CLEAN_NAME_RE = re.compile("[^\w]")

    def __init__(self, desc):
        """Take the decription of a cx_Oracle variable, and make it an actual
        object"""

        # these are the attributes that this item will contain
        for k,v in zip(self.CX_VAR_COLUMNS, desc):
            setattr(self, k, v)

    def element(self, value):
        """Factory for creating an Element for this column"""
        return self.single_element(value, self.name, self.type)

    @classmethod
    def single_element(cls, value, name, data_type):
        """Factory for creating a single Element"""

        name = cls.CLEAN_NAME_RE.sub("", name.lower())

        # XML tags may not start with a digit
        if name[0].isdigit():
            name = "_%s" % name

        elt = etree.Element(name, type=data_type.__name__)
        if value is not None:
            elt.text = str(value)
        return elt

    def __str__(self):
        return "<_DBColumn %s:%s>" % (self.name, self.type)

    def __repr__(self):
        return str(self)


class OracleBase(query.Query):
    """Base query code for both SQL and PL/SQL queries.

    Subclasses must provide _start_oracle()
    """

    def __init__(self, nagcat, conf):
        if not etree or not cx_Oracle:
            raise errors.InitError(
                    "cx_Oracle and lxml are required for Oracle support.")

        super(OracleBase, self).__init__(nagcat, conf)

        for param in ('user', 'password', 'dsn'):
            if param not in conf:
                raise errors.ConfigError('%s is required but missing' % param)
            self.conf[param] = conf[param]

    def _start(self):
        proc = ForkIt(self.conf['timeout'], self._forked)
        return proc.getResult()

    def _forked(self):
        try:
            connection = cx_Oracle.connect(
                    user=self.conf['user'],
                    password=self.conf['password'],
                    dsn=self.conf['dsn'])
            cursor = connection.cursor()
            try:
                return self._forked_query(cursor)
            finally:
                cursor.close()
                connection.close()
        except cx_Oracle.Error, ex:
            return errors.Failure(errors.TestCritical("Oracle query failed: %s" % ex))

    def _forked_query(self, cursor):
        raise Exception("unimplemented")

    def _to_xml(self, cursor, root="queryresult"):
        """Convert a table to XML Elements

        example: select 1 as foo from dual
        <queryresult>
            <row>
                <foo type="NUMBER">1</foo>
            </row>
        </queryresult>
        """

        tree = etree.Element(root)

        # Return empty XML if this wasn't a SELECT
        if not isinstance(cursor.description, list):
            return tree

        columns = map(_DBColumn, cursor.description)
        for row in cursor:
            xmlrow = etree.Element('row')
            for col, val in zip(columns, row):
                xmlrow.append(col.element(val))
            tree.append(xmlrow)
        return tree

    def _to_string(self, cursor):
        return etree.tostring(self._to_xml(cursor), pretty_print=True)


class OracleSQL(OracleBase):
    """Execute a SQL query in Oracle, the result is formatted as XML"""

    classProvides(query.IQuery)

    name = "oracle_sql"

    def __init__(self, nagcat, conf):
        super(OracleSQL, self).__init__(nagcat, conf)
        self.conf['sql'] = conf.get('sql', "select 1 as data from dual")

        if 'parameters' in conf:
            parameters = conf['parameters']
        elif 'binds' in conf: # binds is an alias
            parameters = conf['binds']
        else:
            parameters = []

        if isinstance(parameters, Struct):
            parameters.expand()
            parameters = parameters.dict()
            for key,value in parameters.iteritems():
                if not isinstance(value, (str,int,long,float)):
                    raise errors.ConfigError(
                        "parameter %s is an invalid type" % key)
        elif isinstance(parameters, list):
            for key,value in enumerate(parameters):
                if not isinstance(value, (str,int,long,float)):
                    raise errors.ConfigError(
                        "parameter %s is an invalid type" % key)
        else:
            raise errors.ConfigError("parameters must be a list or struct")

        self.conf['parameters'] = parameters

    def _forked_query(self, cursor):
        cursor.execute(self.conf['sql'], self.conf['parameters'])
        return self._to_string(cursor)


class OracleSQL2(OracleSQL):
    """Alias oraclesql to oracle_sql"""

    classProvides(query.IQuery)
    name = "oraclesql"

    def __init__(self, nagcat, conf):
        super(OracleSQL2, self).__init__(nagcat, conf)
        # So the scheduler's stats are correct
        self.name = "oracle_sql"


class OraclePLSQL(OracleBase):
    """Execute a stored procedure in Oracle, the result is formatted as XML"""

    classProvides(query.IQuery)

    name = "oracle_plsql"

    def __init__(self, nagcat, conf):
        super(OraclePLSQL, self).__init__(nagcat, conf)

        self.conf['procedure'] = conf.get('procedure', None)
        if not self.conf['procedure']:
            raise errors.ConfigError(conf, "procedure is required")

        parameters = conf.get('parameters', None)
        self.conf['parameters'] = []
        if not parameters or not isinstance(parameters, list):
            raise errors.ConfigError(conf,
                    "parameters must be a list of lists")

        for param in parameters:
            self.conf['parameters'].append(
                    self._check_params(conf, param))

    def _check_params(self, conf, param):
        """Check that the parameter definition is valid"""

        if not isinstance(param, list):
            raise errors.ConfigError(conf,
                    "parameters must be a list of lists")

        if len(param) != 3:
            raise errors.ConfigError(conf,
                    ("%s must be a list of three elements: "
                     "[ <in|out> <param_name> <type|value>" % param))

        param[0] = param[0].lower()
        if param[0] not in ('in', 'out'):
            raise errors.ConfigError(conf,
                    "Invalid direction %s, must be 'in' or 'out'" % param[0])

        if param[0] == "out":
            type_name = param[2].upper()
            type_class = getattr(cx_Oracle, type_name, None)
            if not type_class:
                raise errors.ConfigError(conf,
                        "%s is not a valid Oracle type" % param[2])
            param[2] = type_class

        return param

    def _build_params(self, cursor):
        params = []
        for param in self.conf['parameters']:
            if param[0] == "in":
                params.append(param[2])
            elif param[0] == "out":
                params.append(cursor.var(param[2]))
            else:
                assert 0
        return params

    def _forked_query(self, cursor):
        result = cursor.callproc(self.conf['procedure'],
                                 self._build_params(cursor))

        # Convert the 'out' parameters into XML.
        root = etree.Element('result')
        for i, param in enumerate(self.conf['parameters']):
            if param[0] != 'out':
                continue

            if isinstance(result[i], cx_Oracle.Cursor):
                tree = self._to_xml(result[i], param[1])
                root.append(tree)
            else:
                item = _DBColumn.single_element(
                        result[i], param[1], param[2])
                root.append(item)

        return etree.tostring(root, pretty_print=True)
