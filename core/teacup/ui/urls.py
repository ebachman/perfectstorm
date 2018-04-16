from django.conf.urls import url

from teacup.ui import views

urlpatterns = [
    url(r'^$', views.index),
]
