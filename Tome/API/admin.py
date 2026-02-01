from django.contrib import admin
from .models import SolidityContract, ContractInteraction, ContractAsset


@admin.register(SolidityContract)
class SolidityContractAdmin(admin.ModelAdmin):
    """Admin interface for Solidity contracts"""
    list_display = ['name', 'contract_address', 'deployer', 'deployment_block', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'deployer']
    search_fields = ['name', 'contract_address', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Contract Information', {
            'fields': ('name', 'contract_address', 'description', 'is_active')
        }),
        ('Source Code', {
            'fields': ('source_code', 'bytecode', 'abi'),
            'classes': ('collapse',)
        }),
        ('Deployment', {
            'fields': ('deployer', 'deployment_tx', 'deployment_block', 'ipfs_hash')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContractInteraction)
class ContractInteractionAdmin(admin.ModelAdmin):
    """Admin interface for contract interactions"""
    list_display = ['contract', 'user', 'function_name', 'success', 'tx_hash', 'created_at']
    list_filter = ['success', 'created_at', 'contract']
    search_fields = ['function_name', 'tx_hash', 'contract__name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Interaction Details', {
            'fields': ('contract', 'user', 'function_name', 'parameters')
        }),
        ('Transaction', {
            'fields': ('tx_hash', 'block_height', 'success')
        }),
        ('Result', {
            'fields': ('result', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


@admin.register(ContractAsset)
class ContractAssetAdmin(admin.ModelAdmin):
    """Admin interface for contract assets"""
    list_display = ['asset_name', 'contract', 'quantity', 'units', 'reissuable', 'created_at']
    list_filter = ['reissuable', 'has_ipfs', 'created_at']
    search_fields = ['asset_name', 'contract__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Asset Information', {
            'fields': ('contract', 'asset_name', 'quantity', 'units')
        }),
        ('Properties', {
            'fields': ('reissuable', 'has_ipfs', 'ipfs_hash')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

