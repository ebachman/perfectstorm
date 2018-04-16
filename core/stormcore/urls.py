from django.conf.urls import include, url
from django.contrib.staticfiles.views import serve

urlpatterns = [
    url(r'^v1/', include('stormcore.apiserver.urls')),
    url(r'^ui/', include('stormcore.ui.urls')),
    url(r'^static/(?P<path>.*)$', serve, kwargs={'insecure': True}),
]
