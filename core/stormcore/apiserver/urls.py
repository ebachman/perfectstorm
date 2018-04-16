from django.urls import path, include

from rest_framework_mongoengine.routers import DefaultRouter

from stormcore.apiserver import views


router = DefaultRouter(trailing_slash=False)

router.register(r'agents', views.AgentViewSet)
router.register(r'resources', views.ResourceViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'apps', views.ApplicationViewSet)
router.register(r'procedures', views.ProcedureViewSet)
router.register(r'triggers', views.TriggerViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('events', views.EventView.as_view()),
]
