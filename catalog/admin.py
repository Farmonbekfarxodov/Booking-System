from django.contrib import admin

from .models import Provider, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "duration_minutes", "price", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "timezone", "is_active"]
    list_filter = ["is_active", "services"]
    filter_horizontal = ["services"]
