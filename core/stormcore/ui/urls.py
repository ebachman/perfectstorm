from django.conf.urls import url

from stormcore.ui import views

urlpatterns = [
    url(r'^$', views.index),
]
