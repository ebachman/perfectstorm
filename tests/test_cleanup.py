import pytest

from .samples import create_agent, create_group, delete_on_exit


class BaseTestCleanup:

    def check_cleanup(self, dependency, dependent):
        model = type(dependent)

        # Ensure that the dependent object exists
        assert model.objects.filter(id=dependent.id)

        # Delete the dependency: the dependent object should disappear
        # with it
        dependency.delete()
        assert not model.objects.filter(id=dependent.id)


class TestResourceCleanup(BaseTestCleanup):

    def test_agent_deletion(self, agent, resource):
        self.check_cleanup(agent, resource)


class TestGroupCleanup:

    @pytest.fixture()
    def group(self, resource):
        group = create_group(include=[resource.id])
        with delete_on_exit(group):
            yield group

    def test_resource_deletion(self, resource, group):
        assert resource.id in group.include

        resource.delete()
        group.reload()

        assert resource.id not in group.include


class TestSubscriptionCleanup(BaseTestCleanup):

    @pytest.fixture()
    def subscription(self, procedure, resource, alpha_group):
        return procedure.attach(
            group=alpha_group.id, target=resource.id)

    def test_procedure_deletion(self, procedure, subscription):
        self.check_cleanup(procedure, subscription)

    def test_resource_deletion(self, resource, subscription):
        self.check_cleanup(resource, subscription)

    def test_group_deletion(self, alpha_group, subscription):
        self.check_cleanup(alpha_group, subscription)


class TestJobCleanup(BaseTestCleanup):

    @pytest.fixture()
    def job(self, procedure, resource):
        return procedure.exec(target=resource.id, wait=False)

    def test_procedure_deletion(self, procedure, job):
        self.check_cleanup(procedure, job)

    def test_resource_deletion(self, resource, job):
        self.check_cleanup(resource, job)

    def test_agent_deletion(self, agent, job):
        self.check_cleanup(agent, job)

    def test_owner_deletion(self, job):
        assert job.status == 'pending'
        assert job.owner is None

        owner = create_agent()
        job.handle(owner=owner.id)

        assert job.status == 'running'
        assert job.owner == owner.id

        owner.delete()
        job.reload()

        assert job.status == 'pending'
        assert job.owner is None

    def test_owner_offline(self, job):
        assert job.status == 'pending'
        assert job.owner is None

        owner = create_agent()
        job.handle(owner=owner.id)

        assert job.status == 'running'
        assert job.owner == owner.id

        owner.status = 'offline'
        owner.save()
        job.reload()

        assert job.status == 'pending'
        assert job.owner is None
