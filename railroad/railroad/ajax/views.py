from django.http import HttpResponse
from railroad.viewhosts import views

def autocomplete(request, context):
    query = request.GET.get('q', '').lower()
    limit = int(request.GET.get('limit', 10))

    stat, obj = views.parse()

    choices = []

    if context == 'host':
        choices = views.hostnames(stat)
    elif context == 'group':
        choices = [x['alias'] for x in views.grouplist(obj)]
    elif context == 'service':
        choices = views.servicenames(stat)

    matching_names = [x for x in choices if x.lower().startswith(query)]

    result = '\n'.join(matching_names[:limit])


    return HttpResponse(result)
