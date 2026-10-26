from django.contrib import admin
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'company',
        'location',
        'job_type',
        'is_active',
        'posted_at',
    )

    search_fields = ('title', 'company', 'location')
    list_filter = ('job_type', 'is_active')
