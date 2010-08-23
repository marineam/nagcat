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

import os
import sys

# Describes the location of our Django configuration file. Unless you move the
# settings file this default should be fine
os.environ['DJANGO_SETTINGS_MODULE'] = 'railroad.settings'

# These should correspond to the paths of your railroad and nagcat
# installation
sys.path.append('/var/lib/nagcat/railroad')
sys.path.append('/var/lib/nagcat/python')

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
