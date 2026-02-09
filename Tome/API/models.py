from django.db import models
from django.contrib.auth.models import User
import secrets
import hashlib


class SolidityContract(models.Model):
    """
    Model to store Solidity contract deployments for Evrmore stateless contracts.
    This represents a contract deployed on the Evrmore blockchain.
    """
    # Contract identification
    name = models.CharField(max_length=255, help_text="Contract name")
    contract_address = models.CharField(max_length=255, unique=True, help_text="Evrmore asset name or contract identifier")
    
    # Contract source and ABI
    source_code = models.TextField(blank=True, help_text="Solidity source code")
    bytecode = models.TextField(blank=True, help_text="Compiled bytecode")
    abi = models.JSONField(default=list, help_text="Contract ABI (Application Binary Interface)")
    
    # Deployment information
    deployer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deployed_contracts')
    deployment_tx = models.CharField(max_length=255, blank=True, help_text="Transaction hash of deployment")
    deployment_block = models.IntegerField(null=True, blank=True, help_text="Block height of deployment")
    
    # Contract metadata
    description = models.TextField(blank=True, help_text="Contract description")
    ipfs_hash = models.CharField(max_length=255, blank=True, help_text="IPFS hash for contract metadata")
    
    # Contract state
    is_active = models.BooleanField(default=True, help_text="Whether contract is active")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract_address']),
            models.Index(fields=['deployer', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.contract_address})"


class ContractInteraction(models.Model):
    """
    Model to track interactions with deployed contracts.
    This logs function calls and transactions to contracts.
    """
    contract = models.ForeignKey(SolidityContract, on_delete=models.CASCADE, related_name='interactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_contract_interactions')
    
    # Interaction details
    function_name = models.CharField(max_length=255, help_text="Name of function called")
    parameters = models.JSONField(default=dict, help_text="Function parameters")
    
    # Transaction details
    tx_hash = models.CharField(max_length=255, blank=True, help_text="Transaction hash")
    block_height = models.IntegerField(null=True, blank=True, help_text="Block height")
    
    # Result
    success = models.BooleanField(default=False, help_text="Whether interaction was successful")
    result = models.JSONField(default=dict, help_text="Interaction result")
    error_message = models.TextField(blank=True, help_text="Error message if failed")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.function_name} on {self.contract.name} by {self.user.username}"


class ContractAsset(models.Model):
    """
    Model to link Evrmore assets to smart contracts.
    Represents assets managed by or related to a contract.
    """
    contract = models.ForeignKey(SolidityContract, on_delete=models.CASCADE, related_name='assets')
    asset_name = models.CharField(max_length=255, help_text="Evrmore asset name")
    
    # Asset properties
    quantity = models.DecimalField(max_digits=30, decimal_places=8, help_text="Total quantity")
    units = models.IntegerField(default=0, help_text="Divisibility (0-8)")
    reissuable = models.BooleanField(default=False, help_text="Whether asset can be reissued")
    has_ipfs = models.BooleanField(default=False, help_text="Whether asset has IPFS metadata")
    ipfs_hash = models.CharField(max_length=255, blank=True, help_text="IPFS hash")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['contract', 'asset_name']]
        indexes = [
            models.Index(fields=['asset_name']),
            models.Index(fields=['contract', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.asset_name} (Contract: {self.contract.name})"


class APIKey(models.Model):
    """
    Model to store API keys for authenticated API access.
    Each user can have multiple API keys for different applications.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=255, help_text="Descriptive name for this API key")
    
    # Store hashed key for security
    key_hash = models.CharField(max_length=64, unique=True, help_text="SHA256 hash of the API key")
    
    # Display prefix (first 8 chars) for user reference
    key_prefix = models.CharField(max_length=8, help_text="First 8 characters of key for identification")
    
    # Key status
    is_active = models.BooleanField(default=True, help_text="Whether this API key is active")
    
    # Usage tracking
    last_used = models.DateTimeField(null=True, blank=True, help_text="Last time this key was used")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_hash']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
    
    @staticmethod
    def generate_key():
        """Generate a secure random API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_key(key):
        """Hash an API key using SHA256"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def verify_key(self, key):
        """Verify if a provided key matches this API key"""
        return self.key_hash == self.hash_key(key)
