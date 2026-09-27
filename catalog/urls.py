from rest_framework.routers import DefaultRouter

from .views import ProviderViewSet, ServiceViewSet

router = DefaultRouter()
router.register("services", ServiceViewSet, basename="service")
router.register("providers", ProviderViewSet, basename="provider")

urlpatterns = router.urls
