from django.conf.urls import url, include

from rest_framework.routers import DefaultRouter

from teacup.apiserver import views

router = DefaultRouter()
router.register(r'groups', views.GroupViewSet)
router.register(r'apps', views.ApplicationViewSet)
router.register(r'recipes', views.RecipeViewSet)
router.register(r'triggers', views.TriggerViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^query/$', views.query),
]
