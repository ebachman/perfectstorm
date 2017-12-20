import socket
import traceback

from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import ConnectionDoesNotExist
from django.shortcuts import render, redirect

from .models import Message


def get_connection_status(request):
    status = {
        'name': 'Address',
        'type': 'address',
    }

    sock = request.META.get('gunicorn.socket')
    if not sock:
        status['error'] = 'No gunicorn.socket available'
        return status

    host, port = sock.getsockname()
    status['value'] = host

    return status


def get_database_status(name):
    status = {
        'name': name,
        'type': 'database',
    }

    conn = connections[name]

    try:
        conn.ensure_connection()
    except Exception as exc:
        status['error'] = str(exc)
        return status

    fileno = conn.connection.fileno()

    sock = socket.fromfd(fileno, socket.AF_INET, socket.SOCK_STREAM)

    host, port = sock.getpeername()
    status['value'] = '%s:%s' % (host, port)

    return status


def run_migrations():
    conn = connections['primary']

    executor = MigrationExecutor(conn)
    targets = executor.loader.graph.leaf_nodes()

    executor.migrate(targets)


def save(model):
    try:
        model.save()
    except Exception:
        run_migrations()
        model.save()


def index(request):
    if request.method == 'POST':
        content = request.POST.get('content')

        if content:
            message = Message(content=request.POST['content'])

            try:
                save(message)
            except Exception:
                traceback.print_exc()

            return redirect('/')

    status = [
        {
            'name': 'name',
            'value': socket.gethostname(),
            'type': 'hostname',
        },
        {
            'name': 'host',
            'value': request.META['HTTP_HOST'],
            'type': 'http-host',
        },
    ]

    for db_name in ('primary', 'replica'):
        try:
            status.append(get_database_status(db_name))
        except ConnectionDoesNotExist:
            pass

    try:
        message_list = list(Message.objects.all())
    except Exception:
        traceback.print_exc()
        message_list = []

    context = {
        'status': status,
        'message_list': message_list,
    }

    return render(request, 'index.html', context)
