import datetime
import json

from django.db import transaction
from django.db.utils import OperationalError
from django.http import JsonResponse

from rest_framework import status, views, viewsets, exceptions
from rest_framework.decorators import api_view, detail_route
from rest_framework.response import Response

from teacup.apiserver import graph
from teacup.apiserver.models import Group, Application, Recipe, Trigger
from teacup.apiserver.serializers import (
    GroupSerializer, GroupAddRemoveMembersSerializer, ApplicationSerializer, RecipeSerializer, TriggerSerializer)



class MalformedQuery(exceptions.APIException):

    status_code = 400
    default_detail = 'Malformed query'
    default_code = 'malformed_query'


def parse_query(q, param_name='q'):
    if q:
        q = q.strip()

    if not q:
        return graph.Any()

    try:
        json_q = json.loads(q)
    except json.JsonDecodeError:
        raise MalformedQuery({param_name: 'Invalid JSON'})

    try:
        return graph.parse_query(json_q)
    except graph.QueryParseError as exc:
        raise MalformedQuery({param_name: exc.args[0]})


@api_view(['GET'])
def query(request):
    query = parse_query(request.GET.get('q'))
    result_set = graph.run_query(query)

    return Response(result_set)


class GroupViewSet(viewsets.ModelViewSet):

    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    lookup_field = 'name'

    @transaction.atomic
    @detail_route(methods=['GET', 'POST'])
    def members(self, request, name=None):
        group = self.get_object()

        if request.method == 'GET':
            query = parse_query(request.GET.get('q'))
            return Response(group.members(query))

        if request.method == 'POST':
            serializer = GroupAddRemoveMembersSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            add_include = graph.normalize_ids(serializer.validated_data['include'])
            add_exclude = graph.normalize_ids(serializer.validated_data['exclude'])

            # Remove those members that are already in the include/exclude lists.
            add_include.difference_update(group.include)
            add_exclude.difference_update(group.exclude)

            if add_include or add_exclude:
                group.include += add_include
                group.exclude += add_exclude
                group.save()

            return Response({'include': group.include, 'exclude': group.exclude})


class ApplicationViewSet(viewsets.ModelViewSet):

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

    lookup_field = 'name'


class RecipeViewSet(viewsets.ModelViewSet):

    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

    lookup_field = 'name'


class TriggerViewSet(viewsets.ModelViewSet):

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
