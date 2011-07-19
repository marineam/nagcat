'''Make calls out to remote XML-RPC servers.'''

import xmlrpclib
import socket

from django.http import HttpResponse


def xmlrpc(request):
    url = request.GET.get('url', 'http://localhost/')
    command = request.GET.get('command')
    args = request.GET.get('args', '')

    args = args.split(' ')
    args = filter(None, [a.strip() for a in args])

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
