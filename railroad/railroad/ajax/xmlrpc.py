'''Make calls out to remote XML-RPC servers.'''

import xmlrpclib
import socket
import json

from django.http import HttpResponse
from django.conf import settings


def xmlrpc(request):
    url = settings.NAGIOS_XMLRPC_URL
    command = request.GET.get('command')

    args = request.GET.get('args')
    if args:
        args = json.loads(args)
    else:
        args = []

    socket.setdefaulttimeout(10)
    try:
        server = xmlrpclib.ServerProxy(url)
        result = getattr(server, command)(*args)
        return HttpResponse(repr(result))
    except xmlrpclib.Fault, ex:
        return HttpResponse('xmlrpc fault: %s' % ex.faultString, status=500)
    except xmlrpclib.Error, ex:
        return HttpResponse('xmlrpc error: %s' % ex, status=500)
    except socket.error, ex:
        return HttpResponse('socket error: %s' % ex, status=500)
