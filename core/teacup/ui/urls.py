from django.conf.urls import url, include
from django.views.static import serve

from teacup.ui import views

urlpatterns = [
    url(r'^$', views.index),
]
