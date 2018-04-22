import json
import time
from datetime import datetime

import pymongo.cursor
from pymongo.errors import OperationFailure

from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.views.generic import View

from rest_framework import status
from rest_framework.decorators import detail_route
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from mongoengine import DoesNotExist, MultipleObjectsReturned

from rest_framework_mongoengine.viewsets import ModelViewSet

from stormcore.apiserver.models import (
    Agent,
    Application,
    Event,
    Group,
    Procedure,
    Resource,
    StormReferenceField,
    Trigger,
    cleanup_expired_agents,
)

from stormcore.apiserver.serializers import (
    AgentSerializer,
    ApplicationSerializer,
    CreateTriggerSerializer,
    EventSerializer,
    GroupAddRemoveMembersSerializer,
    GroupSerializer,
    ProcedureSerializer,
    ResourceSerializer,
    TriggerCompleteSerializer,
    TriggerHandleSerializer,
    TriggerSerializer,
)


def _traverse_dict(dct):
    if isinstance(dct, dict):
        it = dct.items()
    elif isinstance(dct, list):
        it = enumerate(dct)
    else:
        raise TypeError(type(dct).__name__)

    for key, value in it:
        yield dct, key, value
        if isinstance(value, (dict, list)):
            yield from _traverse_dict(value)


def _resolve_references(model, query):
    refs = []

    for dct, key, value in _traverse_dict(query):
        field = model._fields.get(key)
        if isinstance(field, StormReferenceField):
            refs.append((dct, key, value, field))

    if not refs:
        return query

    for dct, key, value, field in refs:
        doctype = field.document_type

        try:
            document = doctype.objects.only('id').lookup(value)
        except Exception:
            continue

        dct[key] = document.id

    return query


def query_filter(request, queryset):
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

        query = _resolve_references(queryset._document, query)

        queryset = queryset.filter(__raw__=query)

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
            queryset = query_filter(self.request, queryset)
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
            queryset = query_filter(self.request, queryset)
            serializer = ResourceSerializer(queryset, many=True)
            return Response(serializer.data)

        if request.method == 'POST':
            serializer = GroupAddRemoveMembersSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            add_include = Resource.objects.filter(names__in=serializer.validated_data['include'])
            add_exclude = Resource.objects.filter(names__in=serializer.validated_data['exclude'])

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


class ProcedureViewSet(StormViewSet):

    queryset = Procedure.objects.all()
    serializer_class = ProcedureSerializer


class TriggerViewSet(StormViewSet):

    queryset = Trigger.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTriggerSerializer
        else:
            return TriggerSerializer

    @detail_route(methods=['POST'])
    def handle(self, request, **kwargs):
        trigger = self.get_object()

        serializer = TriggerHandleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        agent = serializer.validated_data['agent']

        # Atomically transition the status from 'pending' to 'running', setting the
        # owner at the same time
        qs = Trigger.objects.filter(id=trigger.id, status='pending')
        qs.update(set__status='running', set__owner=agent.id)

        # Check the status of the trigger. Because we used an atomic operation, the
        # scenarios are three:
        #
        # 1. the trigger was not in 'pending' status, and the trigger was left
        #    unchanged;
        # 2. the trigger was in 'pending' status but some other agent handled it
        #    before us: in this case the trigger will now be in status 'running'
        #    but the owner will be different from what we expect;
        # 3. the trigger was in 'pending' status and nobody else other than us
        #    touched it: the update suceeded.
        #
        # Case 3 is what we're interested in; all other cases are errors

        trigger.reload()

        if trigger.status != 'running' or trigger.owner.id != agent.id:
            # Case 1 or 2, error
            return Response(
                {'status': ["Trigger is not in 'pending' state"]},
                status=status.HTTP_409_CONFLICT)

        # Case 3, success
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['POST'])
    def complete(self, request, **kwargs):
        trigger = self.get_object()

        serializer = TriggerCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        result = serializer.validated_data['result']

        if trigger.status != 'running':
            return Response(
                {'status': ["Trigger is not in 'running' state"]},
                status=status.HTTP_409_CONFLICT)

        trigger.owner = None
        trigger.status = 'done'
        trigger.result = result
        trigger.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['POST'])
    def fail(self, request, **kwargs):
        trigger = self.get_object()

        serializer = TriggerCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        result = serializer.validated_data['result']

        if trigger.status != 'running':
            return Response(
                {'status': ["Trigger is not in 'running' state"]},
                status=status.HTTP_409_CONFLICT)

        trigger.owner = None
        trigger.status = 'error'
        trigger.result = result
        trigger.save()

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
