from django.contrib import admin
from .models import IPFSUpload

# Register your models here.
@admin.register(IPFSUpload)
class IPFSUploadAdmin(admin.ModelAdmin):
    list_display = ('user', 'file_stored_on_ipfs', 'ipfs_hash', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'ipfs_hash')
    readonly_fields = ('created_at',)
