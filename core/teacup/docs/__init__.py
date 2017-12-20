import os
import subprocess


DOCS_ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS_SOURCE_PATH = os.path.join(DOCS_ROOT, 'source')
DOCS_BUILD_PATH = os.path.join(DOCS_ROOT, 'build')
DOCS_HTML_PATH = os.path.join(DOCS_BUILD_PATH, 'html')


def build_docs(**kwargs):
    subprocess.check_call(
        ['sphinx-build', '-M', 'html', DOCS_SOURCE_PATH, DOCS_BUILD_PATH],
        **kwargs)
