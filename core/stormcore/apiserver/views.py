import copy
import json
import time
from datetime import datetime

import jinja2.sandbox

import pymongo.cursor
from pymongo.errors import OperationFailure

from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.views.generic import View

from rest_framework import status, mixins
from rest_framework.decorators import detail_route
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from mongoengine import DoesNotExist, MultipleObjectsReturned

from rest_framework_mongoengine.viewsets import (
    ModelViewSet, ReadOnlyModelViewSet)

from stormcore.apiserver.models import (
    Agent,
    Application,
    Event,
    Group,
    Job,
    Procedure,
    Resource,
    StormReferenceField,
    cleanup_expired_agents,
)

from stormcore.apiserver.serializers import (
    AgentSerializer,
    ApplicationSerializer,
    EventSerializer,
    GroupAddRemoveMembersSerializer,
    GroupSerializer,
    JobCompleteSerializer,
    JobHandleSerializer,
    JobSerializer,
    ProcedureExecSerializer,
    ProcedureSerializer,
    ResourceSerializer,
)


def prepare_query(query, model):
    if 'id' in query:
        query['_id'] = query.pop('id')

    for key, value in query.items():
        if key.startswith('$'):
            if isinstance(value, list):
                for item in value:
                    prepare_query(item, model)
            else:
                prepare_query(value, model)
        else:
            field = model._fields.get(key)
            if isinstance(field, StormReferenceField):
                doctype = field.document_type
                try:
                    document = doctype.objects.only('id').lookup(value)
                except Exception:
                    continue
                query[key] = document.id


def query_filter(query, queryset):
    if query:
        query = copy.deepcopy(query)
        prepare_query(query, queryset._document)
        queryset = queryset.filter(__raw__=query)
    return queryset


def request_query_filter(request, queryset):
    """Apply the filter specified with the 'q' parameter, if any."""
    query_string = request.GET.get('q')

    if query_string:
        try:
            query = json.loads(query_string)
        except json.JSONDecodeError as exc:
            detail = {'q': [exc.args[0]]}
            raise MalformedQueryError(detail=detail)

        if not isinstance(query, dict):
            detail = {'q': ['Query must be a dictionary']}
            raise MalformedQueryError(detail=detail)

        queryset = query_filter(query, queryset)

        try:
            # Execute the queryset in order to detect errors with the query
            next(iter(queryset))
        except OperationFailure as exc:
            detail = {'q': [exc.args[0]]}
            raise MalformedQueryError(detail=detail)
        except StopIteration:
            pass

    return queryset


class MalformedQueryError(APIException):

    status_code = 400
    default_detail = 'Malformed query.'
    default_code = 'malformed_query'


class QueryFilterMixin:
    """
    This mixin allows filtering results when the 'q' parameter is provided
    (example: 'GET /v1/resources?q={"names":"foo"}'). This has effect only
    when listing the collection.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method == 'GET' and self.get == self.list:
            queryset = request_query_filter(self.request, queryset)
        return queryset


class LookupMixin:
    """Mixin that allows looking up objects using more than one field."""

    lookup_url_kwarg = 'id'
    lookup_value_regex = '[^/]+'

    def get_object(self):
        value = self.kwargs[self.lookup_url_kwarg]
        queryset = self.filter_queryset(self.get_queryset())

        try:
            return queryset.lookup(value)
        except (DoesNotExist, MultipleObjectsReturned):
            raise Http404


class StormViewSet(LookupMixin, QueryFilterMixin, ModelViewSet):

    pass


class StormReadOnlyViewSet(
        LookupMixin, QueryFilterMixin, ReadOnlyModelViewSet):

    pass


class AgentViewSet(StormViewSet):

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    def dispatch(self, *args, **kwargs):
        cleanup_expired_agents()
        return super().dispatch(*args, **kwargs)

    @detail_route(methods=['POST'])
    def heartbeat(self, request, **kwargs):
        agent = self.get_object()
        agent.heartbeat = datetime.now()
        agent.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceViewSet(StormViewSet):

    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer


class GroupViewSet(StormViewSet):

    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    @detail_route(methods=['GET', 'POST'])
    def members(self, request, id=None):
        cleanup_expired_agents()

        group = self.get_object()

        if request.method == 'GET':
            queryset = group.members()
            queryset = request_query_filter(self.request, queryset)
            serializer = ResourceSerializer(queryset, many=True)
            return Response(serializer.data)

        if request.method == 'POST':
            serializer = GroupAddRemoveMembersSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            add_include = Resource.objects.filter(
                names__in=serializer.validated_data['include'])
            add_exclude = Resource.objects.filter(
                names__in=serializer.validated_data['exclude'])

            if add_include or add_exclude:
                group.include += add_include
                group.exclude += add_exclude
                group.save()

            include = [str(item.id) for item in group.include]
            exclude = [str(item.id) for item in group.exclude]

            return Response({'include': include, 'exclude': exclude})

        raise AssertionError('Unsupported method: %s' % request.method)


class ApplicationViewSet(StormViewSet):

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer


class JinjaQuerySet:

    def __init__(self, queryset, serializer_class):
        self._queryset = queryset
        self._serializer_class = serializer_class

    def _serialize(self, obj):
        serializer = self._serializer_class(obj)
        return serializer.data

    def __len__(self):
        return len(self._queryset)

    def __iter__(self):
        return (self._serialize(obj) for obj in self._queryset)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return JinjaQuerySet(
                self._queryset[index],
                self._serializer_class)
        return self._serialize(self._queryset[index])

    def filter(self, query):
        return JinjaQuerySet(
            query_filter(query, self._queryset),
            self._serializer_class)


class JinjaDocumentClass(JinjaQuerySet):

    def get(self, id):
        return self._serialize(self._queryset.lookup(id))


class JinjaResources(JinjaDocumentClass):

    def __init__(self):
        super().__init__(Resource.objects.all(), ResourceSerializer)


class JinjaGroups(JinjaDocumentClass):

    def __init__(self):
        super().__init__(Group.objects.all(), GroupSerializer)

    def _serialize(self, obj):
        data = super()._serialize(obj)
        data['members'] = JinjaQuerySet(
            obj.members(), ResourceSerializer)
        return data


class ProcedureViewSet(StormViewSet):

    queryset = Procedure.objects.all()
    serializer_class = ProcedureSerializer

    @detail_route(methods=['POST'])
    def exec(self, request, **kwargs):
        procedure = self.get_object()

        serializer = ProcedureExecSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        merged_options = {
            **procedure.options,
            **serializer.validated_data['options']}
        merged_params = {
            **procedure.params,
            **serializer.validated_data['params']}

        env = jinja2.sandbox.SandboxedEnvironment(
            extensions=['jinja2.ext.do'],
            line_statement_prefix='%',
            line_comment_prefix='##')
        template = env.from_string(procedure.content)
        template_params = {
            'groups': JinjaGroups(),
            'resources': JinjaResources(),
            'target': JinjaResources()._serialize(
                serializer.validated_data['target']),
            **merged_params,
        }
        rendered_content = template.render(template_params)

        job = serializer.save(
            content=rendered_content,
            options=merged_options,
            params=merged_params,
        )

        serializer = JobSerializer(job)
        return Response(serializer.data)


class JobViewSet(mixins.DestroyModelMixin, StormReadOnlyViewSet):

    queryset = Job.objects.all()
    serializer_class = JobSerializer

    @detail_route(methods=['POST'])
    def handle(self, request, **kwargs):
        job = self.get_object()

        serializer = JobHandleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        owner = serializer.validated_data['owner']

        # Atomically transition the status from 'pending' to 'running', setting
        # the owner at the same time
        qs = Job.objects.filter(id=job.id, status='pending')
        qs.update(set__status='running', set__owner=owner.id)

        # Check the status of the job. Because we used an atomic operation,
        # the scenarios are three:
        #
        # 1. the job was not in 'pending' status, and the job was left
        #    unchanged;
        # 2. the job was in 'pending' status but some other agent handled it
        #    before us: in this case the job will now be in status 'running'
        #    but the owner will be different from what we expect;
        # 3. the job was in 'pending' status and nobody else other than us
        #    touched it: the update suceeded.
        #
        # Case 3 is what we're interested in; all other cases are errors

        job.reload()

        if job.status != 'running' or job.owner.id != owner.id:
            # Case 1 or 2, error
            return Response(
                {'status': ["Job is not in 'pending' state"]},
                status=status.HTTP_409_CONFLICT)

        # Case 3, success
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['POST'])
    def complete(self, request, **kwargs):
        return self._complete(request, 'done')

    @detail_route(methods=['POST'])
    def fail(self, request, **kwargs):
        return self._complete(request, 'error')

    def _complete(self, request, final_status):
        job = self.get_object()

        serializer = JobCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        result = serializer.validated_data['result']

        if job.status != 'running':
            return Response(
                {'status': ["Job is not in 'running' state"]},
                status=status.HTTP_409_CONFLICT)

        job.owner = None
        job.status = final_status
        job.result = result
        job.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class EventView(View):

    queryset = Event.objects.all()

    # For static responses: default number of events to return if 'count'
    # is not specified
    DEFAULT_COUNT = 128

    # For streaming responses: if no event is transmitted after
    # KEEP_ALIVE_TIME seconds, then an empty blank line is sent
    # to avoid client timeout.
    KEEP_ALIVE_TIME = 10

    def _last_event_id(self):
        last_event = self.queryset.only('id').order_by('-id').first()
        return last_event.id if last_event is not None else -1

    def get(self, request):
        streaming = self.request.GET.get('stream', False)
        from_id = count = None

        try:
            from_id = int(self.request.GET['start'])
        except (KeyError, TypeError, ValueError):
            pass

        try:
            count = int(self.request.GET['count'])
        except (KeyError, TypeError, ValueError):
            pass

        if streaming:
            return self.streaming_response(from_id)
        else:
            return self.static_response(from_id, count)

    def static_response(self, from_id=None, count=None):
        if count is None:
            count = self.DEFAULT_COUNT
        if from_id is None:
            last_event_id = self._last_event_id()
            from_id = last_event_id - count + 1

        qs = self.queryset.filter(
            id__gte=from_id,
            id__lt=from_id + count)

        serializer = EventSerializer(qs, many=True)

        response = HttpResponse(content_type='application/json')
        json.dump(serializer.data, response)

        return response

    def streaming_response(self, from_id=None):
        return StreamingHttpResponse(
            self.iter_realtime_events(from_id),
            content_type='application/json')

    def iter_realtime_events(self, from_id=None):
        if from_id is None:
            last_event_id = self._last_event_id()
        else:
            last_event_id = from_id - 1

        last_line_timestamp = time.time()

        new_events_qs = self.queryset.filter(id__gt=last_event_id)

        # Begin by sending an empty line: this ensures that the response
        # headers are sent by Gunicorn. If we didn't do that, clients would
        # hang in case no events are delivered.
        yield '\n'

        while True:
            cursor = new_events_qs._collection.find(
                new_events_qs._query,
                cursor_type=pymongo.cursor.CursorType.TAILABLE_AWAIT)

            while cursor.alive:
                for doc in cursor:
                    ev = Event._from_son(doc)
                    serializer = EventSerializer(ev)
                    yield json.dumps(serializer.data) + '\n'
                    last_event_id = ev.id

                if time.time() - last_line_timestamp >= self.KEEP_ALIVE_TIME:
                    # If no events are to be sent, send a blank line every
                    # KEEP_ALIVE_TIME seconds to ensure that the connection
                    # is kept alive and does not time out.
                    yield '\n'

                last_line_timestamp = time.time()

                time.sleep(1)
