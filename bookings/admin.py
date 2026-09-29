from django.contrib import admin

from .models import Booking, BookingEvent


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ["from_status", "to_status", "actor", "note", "created_at"]
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    inlines = [BookingEventInline]
    list_display = ["id", "service", "provider", "customer", "start_at", "status", "price"]
    list_filter = ["status", "provider", "service"]
    search_fields = ["customer__username", "customer__email"]
    date_hierarchy = "start_at"
