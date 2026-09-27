from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AvailabilityView, TimeOffViewSet, WorkingHoursViewSet

router = SimpleRouter()
router.register(r"providers/(?P<provider_pk>\d+)/working-hours", WorkingHoursViewSet, basename="working-hours")
router.register(r"providers/(?P<provider_pk>\d+)/time-off", TimeOffViewSet, basename="time-off")

urlpatterns = [path("availability/", AvailabilityView.as_view(), name="availability")] + router.urls
