from pyramid.view import view_defaults
from substanced.sdi import mgmt_view
from substanced.util import get_oid

from . import AuditScribe

@view_defaults(
    permission='sdi.view-auditlog',
    http_cache=0,
    )
class AuditLogEventStreamView(object):
    AuditScribe = AuditScribe # for test replacement
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @mgmt_view(name='auditstream-sse', tab_condition=False)
    def auditstream_sse(self):
        """Returns an event stream suitable for driving an HTML5 EventSource.
           The event stream will contain auditing events.

           Obtain events for the context of the view only::

            var source = new EventSource(
               "${request.sdiapi.mgmt_path(context, 'auditstream-sse')}");
           
           Obtain events for a single OID unrelated to the context::

            var source = new EventSource(
               "${request.sdiapi.mgmt_path(context, 'auditstream-sse', _query={'oid':'12345'})}");

           Obtain events for a set of OIDs::

            var source = new EventSource(
               "${request.sdiapi.mgmt_path(context, 'auditstream-sse', _query={'oid':['12345', '56789']})}");

           Obtain all events for all oids::

            var source = new EventSource(
               "${request.sdiapi.mgmt_path(context, 'auditstream-sse', _query={'all':'1'})}");
           
           The executing user will need to possess the ``sdi.view-auditstream``
           permission against the context on which the view is invoked.
        """
        response = self.request.response
        response.content_type = 'text/event-stream'
        last_event_id = self.request.headers.get('Last-Event-Id')
        scribe = self.AuditScribe(self.context)
        if not last_event_id:
            # first call, set a baseline event id
            gen, idx = scribe.latest_id()
            response.text = compose_message('%s-%s' % (gen, idx))
            return response
        else:
            if self.request.GET.get('all'):
                oids = ()
            elif self.request.GET.get('oid'):
                oids = map(int, self.request.GET.getall('oid'))
            else:
                oids = [get_oid(self.context)]
            gen, idx = map(int, last_event_id.split('-', 1))
            events = scribe.newer(gen, idx, oids=oids)
            for gen, idx, event in events:
                event_id = '%s-%s' % (gen, idx)
                message = compose_message(event_id, event.name, event.payload)
                response.text += message
        return response

def compose_message(eventid, name=None, payload=''):
    msg = 'id: %s\n' % eventid
    if name:
        msg += 'event: %s\n' % name
    msg += 'data: %s\n\n' % payload
    return msg.decode('utf-8')

