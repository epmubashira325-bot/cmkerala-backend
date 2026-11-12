from django.contrib import admin
from .models import ContactEnquiry


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'email', 'subject', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'name', 'email', 'subject', 'message', 'created_at')

    def has_add_permission(self, request):
        return False
