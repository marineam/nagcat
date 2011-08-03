from django.http import HttpResponse, HttpRequest, Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from railroad.permalink.models import Service, ConfiguratorPage
from railroad.viewhosts import views
import json
import base64
import random
import datetime

BASE64 = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
LINK_LENGTH = 6

def random_b64_string(length):
    return ''.join(random.choice(BASE64) for _ in range(length))

def is_duplicate_page(link):
    try:
        ConfiguratorPage.objects.get(link=link)
        return True
    except (ConfiguratorPage.DoesNotExist, AssertionError):
        return False

def generate_link(request):
    """
    Given a list of services, generates a permanent link at which the page
    can be viewed again by others.
    """
    stat, obj = views.parse()
    source = request.POST if request.POST else request.GET

    services = source.get('services', '')
    if 'REMOTE_USER' in request.META and request.META['REMOTE_USER']:
        user = request.META['REMOTE_USER']
    else:
        user = 'anonymous railroad user'

    link = ''
    while not link or is_duplicate_page(link):
        link = random_b64_string(LINK_LENGTH)

    page = ConfiguratorPage(link=link, creation=datetime.datetime.now(), user=user)
    page.save() # Gives it a primary key, id
    page.save_services(json.loads(services))
    page.save()

    return HttpResponse(link)

def retrieve_link(request, link):

    stat,obj = views.parse()

    page = get_object_or_404(ConfiguratorPage, link=link)

    services = page.load_services()

    graphs = []

    for service in services:
        service['isGraphable'] = views.is_graphable(service['host'],
            service['service'])
        service['slug'] = views.slugify(service['host'] + service['service'])
        servicedetail = views.servicedetail(stat, service['host'],
            service['service'])
        servicedetail['is_graphable'] = views.is_graphable(service['host'],
            service['service'])
        servicedetail['slug'] = service['slug']
        html = render_to_response("graph.html",servicedetail).content
        service['html'] = html
        graphs.append(service)

    return views.configurator(request,stat,obj,graphs=graphs)
