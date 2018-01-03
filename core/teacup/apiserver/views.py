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

import datetime
import json

from pymongo.errors import OperationFailure

from django.db import transaction
from django.db.utils import OperationalError

from rest_framework import status
from rest_framework.decorators import detail_route
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet as SqlModelViewSet

from rest_framework_mongoengine.viewsets import ModelViewSet

from teacup.apiserver.models import (
    Application,
    Group,
    Recipe,
    Resource,
    Trigger,
)

from teacup.apiserver.serializers import (
    ApplicationSerializer,
    GroupAddRemoveMembersSerializer,
    GroupSerializer,
    RecipeSerializer,
    ResourceSerializer,
    TriggerSerializer,
)


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


class ResourceViewSet(QueryFilterMixin, ModelViewSet):

    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer

    lookup_field = 'names'


class GroupViewSet(QueryFilterMixin, ModelViewSet):

    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    lookup_field = 'name'

    @detail_route(methods=['GET', 'POST'])
    def members(self, request, name=None):
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


class ApplicationViewSet(QueryFilterMixin, ModelViewSet):

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

    lookup_field = 'name'


class RecipeViewSet(SqlModelViewSet):

    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

    lookup_field = 'name'


class TriggerViewSet(SqlModelViewSet):

    queryset = Trigger.objects.all()
    serializer_class = TriggerSerializer

    lookup_field = 'uuid'

    def get_queryset(self):
        queryset = self.queryset.all()

        name = self.request.query_params.get('name')
        status = self.request.query_params.get('status')

        if name:
            queryset = queryset.filter(name=name)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    @detail_route(methods=['POST'])
    def handle(self, request, uuid=None):
        try:
            with transaction.atomic():
                trigger = self.get_object()

                if trigger.status != 'pending':
                    raise OperationalError

                trigger.status = 'running'
                trigger.save()
        except OperationalError as exc:
            return Response(
                {'status': ["Trigger is not in 'pending' state"]},
                status=status.HTTP_409_CONFLICT)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['POST'])
    def heartbeat(self, request, uuid=None):
        trigger = self.get_object()
        trigger.heartbeat = datetime.datetime.now()
        trigger.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
