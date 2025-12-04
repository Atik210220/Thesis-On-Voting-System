from django.contrib import admin
from .models import TamperAlert

@admin.register(TamperAlert)
class TamperAlertAdmin(admin.ModelAdmin):
    list_display = ('created_at','summary','acknowledged')
    list_filter = ('acknowledged',)
    search_fields = ('summary','detail')
