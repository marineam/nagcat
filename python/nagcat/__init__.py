# Copyright 2008-2009 ITA Software, Inc.
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

"""Nagcat: The Nagios Helpful Pet"""

from twisted.python import versions
import twisted
import coil

# Make sure we have the right coil version
if getattr(coil, '__version_info__', (0,0)) < (0,3,14):
    raise ImportError("coil >= 0.3.14 is required")

# Require Twisted >= 8.2, older versions had problematic bugs
if twisted.version < versions.Version('twisted', 8, 2, 0):
    raise ImportError("Twisted >= 8.2 is required")
