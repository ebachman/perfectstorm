from django.views.static import serve

from teacup import docs


def documentation(request, path):
    if not path or path.endswith('/'):
        path += 'index.html'
    return serve(request, path, docs.DOCS_HTML_PATH)
