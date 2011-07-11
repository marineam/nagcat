from django.http import HttpResponse
from railroad.viewhosts import views
import itertools
import json

def transpose_combo(li, n, memo):
    """
    Give the right set of auto complete suggestions for repeated start strings.

    Note that if called with the same inputs multiple times different values
    will be returned, quite on purpose.
    """

    key = repr(li)
    if key in memo:
        return memo[key].next()

    n = min(n,len(li))
    combinations = itertools.combinations(li,n)
    transpose = zip(*combinations)
    memo[key] = iter(transpose)
    return memo[key].next()

def autocomplete(request, context):
    """
    Given a query in a GET parameter, give a list of auto complete suggestions.
    Supports having multiple incomplete values in a comma seperated list.
    """

    query = request.GET.get('term', '')
    limit = int(request.GET.get('limit', 10))

    stat, obj = views.parse()

    choices = []
    queries = []
    q_results = []

    queries = [q.strip() for q in query.split(',') if q.strip()]

    if context == 'host':
        choices = views.hostnames(stat)
    elif context == 'group':
        choices = [x['alias'] for x in views.grouplist(obj)]
    elif context == 'service':
        # servicesnames will return services with the sane name for different
        # hosts, so we make it a set to get rid of duplicate names
        choices = set(views.servicenames(stat))

    for q in queries:
        matching_names = [x for x in choices if q.lower() in x.lower()]
        q_results.append(matching_names)

    # this craziness is to deal with this situation: let valid completions be
    # 'ab', 'ac'. User enters "a, a". Auto complete should give back ['ab,
    # ac'], not ['ab, ac', 'ac, ab'].
    memo = {}
    counts = {}
    for q in q_results:
        key = repr(q) # lists aren't hashable :( but strings are :)
        if key in counts:
            counts[key] += 1
        else:
            counts[key] = 1

    product_foder = []
    for q in q_results:
        try:
            product_foder.append(transpose_combo(q, counts[repr(q)], memo))
        except StopIteration:
            # That means the user entered too many of the substring. ignore an
            # excess entries.
            pass
    # end craziness

    results = itertools.product(*product_foder)
    results = [','.join(result) for result in itertools.islice(results, limit)]
    result = [ { "value" : r } for r in results ]

    return HttpResponse(json.dumps(result))
