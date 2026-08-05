from django.contrib import admin
from .models import AddressMetadataTag, IPFSUpload

# Register your models here.
@admin.register(IPFSUpload)
class IPFSUploadAdmin(admin.ModelAdmin):
    list_display = ('user', 'file_stored_on_ipfs', 'ipfs_hash', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'ipfs_hash')
    readonly_fields = ('created_at',)


@admin.register(AddressMetadataTag)
class AddressMetadataTagAdmin(admin.ModelAdmin):
    list_display = ('asset_name', 'target_address', 'user', 'status', 'transaction_id', 'created_at')
    list_filter = ('status', 'tag_type', 'created_at')
    search_fields = ('asset_name', 'target_address', 'transaction_id', 'ipfs_cid', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'last_verified_at')
