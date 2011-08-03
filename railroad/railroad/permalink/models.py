from django.db import models

from django.http import HttpResponse
from railroad.viewhosts.views import slugify
import json


class Service(models.Model):
    host = models.CharField(max_length=50)
    service = models.CharField(max_length=50)
    start = models.IntegerField()
    end = models.IntegerField()
    uniq = models.IntegerField()

    def __unicode__(self):
        return slugify(self.host + self.service)
    def __repr__(self):
        return slugify('< ' +self.host + self.service + ' >')

class ConfiguratorPage(models.Model):
    link = models.CharField(max_length=20)
    services = models.ManyToManyField(Service)
    creation = models.DateTimeField('date created')
    user = models.CharField(max_length=30)

    def __unicode__(self):
        return self.link

    def save_services(self,service_dict):
        for s in service_dict:
            if not s:
                continue
            host = s['host']
            service = s['service']
            if s.has_key('start'):
                start = s['start']
            else:
                start = 0
            if s.has_key('end'):
                end = s['end']
            else:
                end = 0
            if s.has_key('uniq'):
                uniq = s['uniq']
            else:
                uniq = 0
            self.services.create(host=host, service=service,
              start=start, end=end, uniq=uniq)

    def load_services(self):
        service_list = []
        for s in self.services.all():
            host = s.host
            servicename = s.service
            start = s.start
            end = s.end
            uniq = s.uniq
            service = {
                "host" : host,
                "service": servicename,
                "start": start,
                "end": end,
                "uniq": uniq,
            }
            service_list.append(service)
        return service_list



