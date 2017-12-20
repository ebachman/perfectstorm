from django.conf import settings


class PrimaryReplicaRouter:

    def db_for_read(self, model, **hints):
        if 'replica' in settings.DATABASES:
            return 'replica'
        else:
            return 'primary'

    def db_for_write(self, model, **hints):
        return 'primary'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
