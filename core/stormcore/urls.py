from django.contrib.staticfiles.views import serve
from django.urls import path, include

urlpatterns = [
    path('v1/', include('stormcore.apiserver.urls')),
    path('ui/', include('stormcore.ui.urls')),
    path('static/<path>', serve, kwargs={'insecure': True}),
]
