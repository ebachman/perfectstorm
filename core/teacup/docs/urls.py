from django.conf.urls import url, include
from django.views.static import serve

from teacup.docs import views

urlpatterns = [
    url(r'^(?P<path>.*)$', views.documentation),
]
