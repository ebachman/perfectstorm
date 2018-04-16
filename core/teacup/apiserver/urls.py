from django.conf.urls import url, include

from rest_framework_mongoengine.routers import DefaultRouter

from teacup.apiserver import views


router = DefaultRouter(trailing_slash=False)

router.register(r'agents', views.AgentViewSet)
router.register(r'resources', views.ResourceViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'apps', views.ApplicationViewSet)
router.register(r'procedures', views.ProcedureViewSet)
router.register(r'triggers', views.TriggerViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^events$', views.EventView.as_view()),
]
