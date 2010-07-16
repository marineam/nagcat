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

from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    (r'^parserrd/(?P<host>.+)/(?P<data>.+)/(?P<start>[0-9]+)/(?P<end>[0-9]+)/(?P<resolution>[0-9]+)/$', 'railroad.parserrd.views.index'),
    (r'^pagetest/$', 'railroad.pagetest.views.index'),
    (r'^$', 'railroad.viewhosts.views.index'),

    (r'^viewhost/(?P<host>\w+)$', 'railroad.viewhosts.views.host'),
    (r'^viewhost/(?P<host>\w+)/(?P<service>.+)$', 'railroad.viewhosts.views.service'),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/', include(admin.site.urls)),
)
