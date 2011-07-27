from django.http import HttpResponse, HttpRequest, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from railroad.permalink.models import Service, ConfiguratorPage
from railroad.viewhosts import views
import json
import base64
import random
import datetime

BASE64_LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
LINK_LENGTH = 6

def random_b64_string(length):
    return ''.join(random.choice(BASE64_LETTERS) for _ in range(length))

def is_duplicate_page(link):
    try:
        ConfiguratorPage.objects.get(link=link)
        return True
    except (ConfiguratorPage.DoesNotExist, AssertionError):
        return False

def generate_link(request):
    """Given a list of services, generates a permanent link at which the page can be viewed again by others"""

    stat, obj = views.parse()

    source = request.POST if request.POST else request.GET

    services = source.get('services', '')

    link = random_b64_string(LINK_LENGTH)

    while is_duplicate_page(link):
        link = random_b64_string(LINK_LENGTH)

    page = ConfiguratorPage(link=link, creation=datetime.datetime.now())
    page.save() # Gives it a primary key, id
    page.save_services(json.loads(services))
    page.save()

    return HttpResponse(link)

def retrieve_link(request, link):

    stat,obj = views.parse()

    page = get_object_or_404(ConfiguratorPage, link=link)

    services = page.load_services()

    loaded_graphs = []

    for service in services:
        so = views.servicedetail(stat, service['host'], service['service'])
        if so:
            so['start'] = service['start']
            so['end'] = service['end']
            so['uniq'] = service['uniq']
            so['slug'] = views.slugify(service['host'] + service['service'])
            so['period'] = 'ajax'
            so['is_graphable'] = views.is_graphable(service['host'], service['service'])
            loaded_graphs.append(so)

    return views.configurator(request,stat,obj,loaded_graphs=loaded_graphs)
