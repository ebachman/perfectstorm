from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^docs/', include('teacup.docs.urls')),
    url(r'^v1/', include('teacup.apiserver.urls')),
    url(r'^ui/', include('teacup.ui.urls')),
]

urlpatterns += staticfiles_urlpatterns()
