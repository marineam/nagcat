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

from django.conf import settings
from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Index page
    (r'^$', 'railroad.viewhosts.views.index'),


    # Permalinks
    (r'^permalink/generate/', 'railroad.permalink.views.generate_link'),
    (r'^permalink/(?P<link>[A-Za-z0-9_\-]+)$',
        'railroad.permalink.views.retrieve_link'),
    (r'^permalinks/', 'railroad.permalink.views.list_links'),
    (r'^permalink/delete/(?P<link>[A-Za-z0-9_\-]+)$',
        'railroad.permalink.views.delete_link'),

    # Viewers
    (r'^graphs/?$', 'railroad.viewhosts.views.graphs'),
    (r'^viewhost/(?P<host>\w+)/(?P<service>.+)$',
        'railroad.viewhosts.views.service'),
    (r'^viewgroup/(?P<group>[^/]+)$', 'railroad.viewhosts.views.group'),
    # Configurator and helper functions for AJAX
    (r'^configurator$', 'railroad.viewhosts.views.directconfigurator'),
    (r'^configurator/graph$', 'railroad.viewhosts.views.customgraph'),
    (r'^configurator/host/(?P<hosts>\w+)$',
        'railroad.viewhosts.views.hostconfigurator'),
    (r'^configurator/service/(?P<service>(\w+\s*)+)$',
        'railroad.viewhosts.views.serviceconfigurator'),

    # Downtime page
    (r'^downtime', 'railroad.viewhosts.views.downtime'),

    # Stuff for AJAX
    (r'^configurator/meta$', 'railroad.viewhosts.views.meta'),
    (r'^configurator/service_meta$',
        'railroad.viewhosts.views.service_page_meta'),
    (r'^ajax/autocomplete/(?P<context>\w+)?$',
        'railroad.ajax.autocomplete.autocomplete'),
    (r'^ajax/xmlrpc$', 'railroad.ajax.xmlrpc.xmlrpc'),
    (r'^404$', 'django.views.defaults.page_not_found'),

    # Pass js files through the template processor to handle URLs
    url(r'^(?P<template>js/\w+.js)$',
        'django.views.generic.simple.direct_to_template',
        {'mimetype': 'text/javascript'}, name='js'),
)

if getattr(settings, 'RAILROAD_STATIC', None):
    urlpatterns += patterns('',
        (r'^railroad-static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.RAILROAD_STATIC}))
