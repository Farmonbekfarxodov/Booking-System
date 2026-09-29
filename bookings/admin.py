from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "service", "provider", "customer", "start_at", "status", "price"]
    list_filter = ["status", "provider", "service"]
    search_fields = ["customer__username", "customer__email"]
    date_hierarchy = "start_at"
