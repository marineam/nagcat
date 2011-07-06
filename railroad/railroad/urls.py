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

# Set our custom 404 handler to make sure the sidebar works
handler404 = 'railroad.viewhosts.views.error404'

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Index page
    (r'^$', 'railroad.viewhosts.views.index'),

    # parserrd backend
    (r'^parserrd/(?P<host>.+)/(?P<service>.+)/(?P<start>[0-9]+)/(?P<end>[0-9]+)/(?P<resolution>[0-9]+)/?$', 'railroad.parserrd.views.index'),

    # Test functions
#    (r'^pagetest/$', 'railroad.pagetest.views.index'),
    (r'^test$', 'railroad.viewhosts.views.form'),

    # Viewers
    (r'^viewhost/(?P<host>\w+)$', 'railroad.viewhosts.views.graphpage'),
    (r'^viewhost/(?P<host>\w+)/(?P<service>.+)$', 'railroad.viewhosts.views.service'),
    (r'^viewgroup/(?P<group>[^/]+)$', 'railroad.viewhosts.views.group'),
    (r'^viewgroup/(?P<group>[^/]+)/(?P<test>.+)/(?P<alias>.+)$', 'railroad.viewhosts.views.groupservice'),
    # Configurator and helper functions for AJAX
    (r'^graphs', 'railroad.viewhosts.views.graphpage'),
    (r'^c/(?P<id>\d+)$', 'railroad.viewhosts.views.directurl'),
    (r'^configurator$', 'railroad.viewhosts.views.directconfigurator'),
    (r'^configurator/graph$', 'railroad.viewhosts.views.customgraph'),
    (r'^configurator/formstate$', 'railroad.viewhosts.views.formstate'),
    (r'^configurator/generatelink$', 'railroad.viewhosts.views.generatelink'),
    (r'^configurator/host/(?P<hosts>\w+)$', 'railroad.viewhosts.views.hostconfigurator'),
    (r'^configurator/service/(?P<service>(\w+\s*)+)$', 'railroad.viewhosts.views.serviceconfigurator'),

    # Stuff for AJAX
    (r'^ajax/autocomplete/(?P<context>\w+)$', 'railroad.ajax.views.autocomplete'),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/', include(admin.site.urls)),
)
