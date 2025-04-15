from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RideViewSet, LocationViewSet, RidePassengerViewSet

router = DefaultRouter()
router.register('rides', RideViewSet)
router.register('locations', LocationViewSet)
router.register('ride-passengers', RidePassengerViewSet)

urlpatterns = [
    path('', include(router.urls)),
]