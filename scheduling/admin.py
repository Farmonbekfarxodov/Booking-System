from django.contrib import admin

from .models import TimeOff, WorkingHours


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ["provider", "weekday", "start_time", "end_time"]
    list_filter = ["provider", "weekday"]


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ["provider", "start_at", "end_at", "reason"]
    list_filter = ["provider"]
