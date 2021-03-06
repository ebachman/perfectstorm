import textwrap
import time
from multiprocessing import Process, Barrier, Queue

import pytest

from stormlib import Procedure, Job
from stormlib.exceptions import StormConflictError

from .create import BaseTestCreateWithAgent
from .samples import create_agent, create_procedure, delete_on_exit
from .stubs import IDENTIFIER, PLACEHOLDER


class TestCreate(BaseTestCreateWithAgent):

    model = Procedure

    default_procedure = {
        'id': IDENTIFIER,
        'type': PLACEHOLDER,
        'name': None,
        'content': '',
        'params': {},
        'options': {},
    }

    valid_data = [
        (
            {'type': 'test'},
            {**default_procedure, 'type': 'test'},
        ),
        (
            {'type': 'test', 'content': 'hello'},
            {**default_procedure, 'type': 'test',
             'content': 'hello'},
        ),
        (
            {'type': 'test', 'params': {'x': 'y'}},
            {**default_procedure, 'type': 'test', 'params': {'x': 'y'}},
        ),
        (
            {'type': 'test', 'options': {'i': 'j'}},
            {**default_procedure, 'type': 'test', 'options': {'i': 'j'}},
        ),
        (
            {
                'type': 'test', 'content': 'hello',
                'params': {'x': 'y'}, 'options': {'i': 'j'},
            },
            {**default_procedure,
             'type': 'test',
             'content': 'hello',
             'params': {'x': 'y'},
             'options': {'i': 'j'}},
        ),
    ]

    invalid_data = [
        (
            {},
            'type: Field cannot be None',
            {'type': ['This field is required.']},
        ),
    ]


class TestJobs:

    def test_lifecycle(self, agent, procedure, resource):
        job = procedure.exec(target=resource.id, wait=False)

        assert job.status == 'pending'
        assert job.is_pending()
        assert not job.is_running()
        assert not job.is_complete()

        job.handle(owner=agent.id)

        assert job.status == 'running'
        assert not job.is_pending()
        assert job.is_running()
        assert not job.is_complete()

        job.complete()

        assert job.status == 'done'
        assert not job.is_pending()
        assert not job.is_running()
        assert job.is_complete()

    def test_concurrency(self, procedure, resource):
        # In this test we are going to start several processes trying to
        # handle the same job at the same time. Only one of those processes
        # should succeed, the others should fail with 409 Conflict.
        proc_count = 64
        job = procedure.exec(target=resource.id, wait=False)

        # Barrier is used to make the processess call handle() at the same
        # time
        barrier = Barrier(proc_count)
        # Queue is used to collect the results from the processess: either
        # 'success' or 'conflict'
        queue = Queue()

        def inner():
            agent = create_agent()

            # Wait for all other processess to start and complete agent
            # creation
            barrier.wait()

            try:
                job.handle(owner=agent.id)
            except StormConflictError:
                queue.put((agent.id, 'conflict'))
            else:
                queue.put((agent.id, 'success'))

        # Start all processes
        procs = [
            Process(target=inner, daemon=True)
            for i in range(proc_count)
        ]

        for proc in procs:
            proc.start()

        # Join the procs and get their results, waiting at most 10
        # seconds
        max_time = time.time() + 10

        for proc in procs:
            proc.join(timeout=max_time - time.time())

        results = dict(
            queue.get(timeout=max_time - time.time())
            for i in range(proc_count)
        )

        # Check that the results contain exactly 1 'success' and all the
        # others are 'conflict'
        assert len(results) == proc_count

        statuses = list(results.values())
        assert statuses.count('success') == 1
        assert statuses.count('conflict') == proc_count - 1

        # Check that the agent that reported 'success' is effectively
        # the owner of the job
        expected_owner, = (
            owner for owner, status in results.items()
            if status == 'success')

        job.reload()
        assert job.owner == expected_owner

    def test_wait(self, agent, procedure, resource):
        def handle_job():
            with job.handle(owner=agent.id):
                # Pretend to do some work
                time.sleep(2)

        job = procedure.exec(target=resource.id, wait=False)

        process = Process(target=handle_job)
        process.start()

        try:
            job.wait()
        finally:
            process.join()

        assert job.is_complete()

    def test_content_rendering(self, agent, procedure, resource):
        job = procedure.exec(target=resource.id, wait=False)
        assert job.content == '1 + 2 = 3'


class TestSubscriptions:

    @pytest.fixture()
    def procedure(self):
        procedure = create_procedure(
            content=textwrap.dedent('''\
                Type: {{ event.event_type }}
                Entity Type: {{ event.entity_type }}
                Entity ID: {{ event.entity_id }}
                Entity Names: {{ event.entity_names }}
                '''),
        )

        with delete_on_exit(procedure):
            yield procedure

    def test_subscriptions(self, procedure, random_resources, alpha_group):
        subscription = procedure.attach(
            group=alpha_group.id,
            target=random_resources[0].id,
        )
        assert subscription.id is not None
        assert not Job.objects.filter(procedure=procedure.id)

        # Trigger an update
        resource = alpha_group.members()[0]
        resource.save()

        # As a consequence of the update, a new job should have been
        # triggered. Wait for it to appear (for no more than 10 seconds)
        max_time = time.time() + 10

        while time.time() < max_time:
            if Job.objects.filter(procedure=procedure.id):
                break
            time.sleep(.5)

        assert len(Job.objects.filter(procedure=procedure.id)) == 1

        job = Job.objects.get(procedure=procedure.id)
        expected_content = textwrap.dedent('''\
            Type: updated
            Entity Type: resource
            Entity ID: {}
            Entity Names: {}
            '''.format(resource.id, resource.names))

        assert job.content == expected_content.strip()
