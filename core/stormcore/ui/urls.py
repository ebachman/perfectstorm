from django.urls import path

from stormcore.ui import views

urlpatterns = [
    path('', views.index),
]
