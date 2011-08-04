from django.http import HttpResponse, HttpRequest, Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.template import Context, loader
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

def get_user(request):
    if 'REMOTE_USER' in request.META and request.META['REMOTE_USER']:
        user = request.META['REMOTE_USER']
    else:
        user = 'anonymous railroad user'
    return user

def generate_link(request):
    """
    Given a list of services, generates a permanent link at which the page
    can be viewed again by others.
    """
    stat, obj = views.parse()
    source = request.POST if request.POST else request.GET

    services = source.get('services', '')
    user = get_user(request)

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

def list_links(request):

    stat,obj = views.parse()

    user = get_user(request)
    page = ConfiguratorPage.objects.filter(user=user)
    template = loader.get_template('permalinks.html')
    services = stat['service']

    context_data = {'services': services}
    context_data = views.add_hostlist(stat, obj, context_data)
    context_data['configurator_page'] = page
    c = Context(context_data)

    return HttpResponse(template.render(c))

def delete_link(request, link):

    page = get_object_or_404(ConfiguratorPage, link=link)

    user = get_user(request)
    if user == page.user:
        page.delete()
        return HttpResponse("The link " + link + " has been deleted")
    else:
        return HttpResponse("You are not " + user +
            ", and there for cannot delete this link")
