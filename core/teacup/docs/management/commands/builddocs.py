import subprocess

from django.core.management.base import BaseCommand, CommandError

from teacup import docs


class Command(BaseCommand):

    help = 'Build the documentation using Sphinx'

    def handle(self, *args, **options):
        try:
            docs.build_docs(
                stdout=self.stdout,
                stderr=self.stderr)
        except subprocess.CalledProcessError as exc:
            raise CommandError('sphinx-build failed: %s' % exc)
