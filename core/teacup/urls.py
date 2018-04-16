from django.conf.urls import include, url
from django.contrib.staticfiles.views import serve

urlpatterns = [
    url(r'^v1/', include('teacup.apiserver.urls')),
    url(r'^ui/', include('teacup.ui.urls')),
    url(r'^static/(?P<path>.*)$', serve, kwargs={'insecure': True}),
]
