from django.http import HttpResponse
from railroad.viewhosts import views
import itertools
import json

def autocomplete(request, context):
    query = request.GET.get('term', '')
    limit = int(request.GET.get('limit', 10))


    stat, obj = views.parse()

    choices = []
    queries = []
    q_results = []
    res = {}

    if len(query.split(',')) > 1:
        queries = query.split(',')
    else:
        queries = [query]

    queries = [q.strip() for q in queries if q.strip()]

    if context == 'host':
        choices = views.hostnames(stat)
    elif context == 'group':
        choices = [x['alias'] for x in views.grouplist(obj)]
    elif context == 'service':
        # servicesnames will return services with the sane name for different hosts, so
        # we make it a set to get rid of duplicate names
        choices = set(views.servicenames(stat))

    for q in queries:
        matching_names = [x for x in choices if x.lower().startswith(q)]
        q_results.append(matching_names)
    results = itertools.product(*q_results)
    results = [','.join(result) for result in results]
    result = [ { "value" : r } for r in results ] 
    return HttpResponse(json.dumps(result))
