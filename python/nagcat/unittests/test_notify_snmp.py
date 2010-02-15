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

from email.message import Message
from twisted.internet import reactor
from twisted.trial import unittest
from nagcat import notify
from nagcat.plugins import notify_smtp
from nagcat.unittests import dummy_server
from nagcat.unittests import test_notify
import coil


class EmailNotificationTest(unittest.TestCase):

    notification = notify_smtp.EmailNotification
    address = test_notify.ENVIRONMENT_HOST['NAGIOS_CONTACTEMAIL']

    def setUp(self):
        self.macros = {
                'host': notify.Macros(test_notify.ENVIRONMENT_HOST),
                'service': notify.Macros(test_notify.ENVIRONMENT_SERVICE)}
        self.factory = dummy_server.SMTP()
        self.server = reactor.listenTCP(0, self.factory)
        self.config = coil.parse(notify.DEFAULT_CONFIG)
        self.config.merge(coil.struct.Struct(self.notification.defaults))
        self.config['smtp.port'] = self.server.getHost().port

    def testPlugin(self):
        plugins = notify.get_notify_plugins()
        self.assertIn(self.notification.name, plugins)

    def testNotifyHost(self):
        return self._send('host', self.config)

    def testNotifyServce(self):
        return self._send('service', self.config)

    def _send(self, type_, config):
        obj = self.notification(type_, self.macros[type_], self.config)

        def check(msg):
            macros = self.macros[type_]
            self.assertIsInstance(msg, Message)
            self.assertEquals(msg['Subject'], obj.subject())
            self.assertEquals(msg['To'], self.address)
            self.assertEquals(msg['X-Nagios-Notification-Type'],
                              macros['NOTIFICATIONTYPE'])
            return msg

        d = obj.send()
        d.addCallback(lambda x: self.factory.message)
        d.addCallback(check)
        return d

    def tearDown(self):
        return self.server.loseConnection()

class PagerNotificationTest(EmailNotificationTest):

    notification = notify_smtp.PagerNotification
    address = test_notify.ENVIRONMENT_HOST['NAGIOS_CONTACTPAGER']
