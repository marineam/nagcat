# Copyright 2008-2011 Google, Inc.
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

from twisted.internet import defer

from nagcat import log, test, scheduler, simple

class NagcatMerlinTestDummy(scheduler.Scheduler):
    """For testing purposes."""
    def build_tests(self, config):
        return []

    def nagios_status(self):
        return simple.ObjectDummy()

    def get_peer_id_num_peers(self):
        return 0,2

class MerlinTest(test.Test):

    def __init__(self, nagcat, conf, test_index):
        test.Test.__init__(self, nagcat, conf)
        self._test_index = test_index

    def _should_run(self):
        """Decides whether or not a test should be run, based on its task
        index and the schedulers peer_id. Returns True if it should run, False
        if it should not."""
        peer_id, num_peers = self._nagcat.get_peer_id_num_peers()
        log.debug("Running should_run, test_index=%s, num_peers=%s, peer_id=%s",
            str(self._test_index), num_peers, peer_id)
        if peer_id and num_peers:
            if self._test_index % num_peers != peer_id:
                return False
        return True

    def start(self):
        """Decides whether or not to start the test, based on _should_run."""
        if self._should_run():
            log.debug("Running test %s", self)
            return super(MerlinTest,self).start()
        else:
            log.debug("Skipping start of %s", self)
            return defer.succeed(None)
