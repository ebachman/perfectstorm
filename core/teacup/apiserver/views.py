# Copyright (c) 2017, Composure.ai
# Copyright (c) 2018, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

import json
from datetime import datetime

from pymongo.errors import OperationFailure

from rest_framework import status
from rest_framework.decorators import detail_route
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from mongoengine.queryset import Q

from rest_framework_mongoengine.generics import get_object_or_404
from rest_framework_mongoengine.viewsets import ModelViewSet

from teacup.apiserver.models import (
    Agent,
    Application,
    Group,
    Procedure,
    Resource,
    StormReferenceField,
    Trigger,
    cleanup_expired_agents,
)

from teacup.apiserver.serializers import (
    AgentSerializer,
    ApplicationSerializer,
    CreateTriggerSerializer,
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


class MultiLookupMixin:
    """Mixin that allows looking up objects using more than one field."""

    lookup_url_kwarg = 'id'

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        filter_query = Q()
        value = self.kwargs[self.lookup_url_kwarg]

        for field in queryset._document._meta['lookup_fields']:
            filter_query |= Q(**{field: value})

        return get_object_or_404(queryset, filter_query)


class CleanupAgentsMixin:

    def dispatch(self, *args, **kwargs):
        cleanup_expired_agents()
        return super().dispatch(*args, **kwargs)


class AgentViewSet(CleanupAgentsMixin, QueryFilterMixin, ModelViewSet):

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    lookup_field = 'id'

    @detail_route(methods=['POST'])
    def heartbeat(self, request, **kwargs):
        agent = self.get_object()
        agent.heartbeat = datetime.now()
        agent.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceViewSet(CleanupAgentsMixin, MultiLookupMixin, QueryFilterMixin, ModelViewSet):

    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer


class GroupViewSet(MultiLookupMixin, QueryFilterMixin, ModelViewSet):

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


class ApplicationViewSet(MultiLookupMixin, QueryFilterMixin, ModelViewSet):

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer


class ProcedureViewSet(MultiLookupMixin, QueryFilterMixin, ModelViewSet):

    queryset = Procedure.objects.all()
    serializer_class = ProcedureSerializer


class TriggerViewSet(CleanupAgentsMixin, QueryFilterMixin, ModelViewSet):

    queryset = Trigger.objects.all()

    lookup_field = 'id'

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
        qs.update(set__status='running', set__owner=agent)

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

        if trigger.status != 'running' or trigger.owner.id != agent:
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
