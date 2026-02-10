from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class IPFSUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ipfs_uploads')
    # Do NOT instantiate the IPFS storage at import time; some environments
    # won't have the IPFS daemon available and importing the storage
    # implementation can raise/attempt network calls. Use a plain FileField
    # and perform IPFS operations lazily at runtime.
    file_stored_on_ipfs = models.FileField(blank=True, null=True)
    ipfs_hash = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = getattr(self.file_stored_on_ipfs, 'name', '') or ''
        return f"IPFSUpload(file_name={name}, ipfs_hash={self.ipfs_hash})"

    def upload_to_ipfs(self):
        """Attempt to upload the current file to IPFS using the optional
        `ipfs_storage` package. This imports the IPFS storage lazily so
        Django tooling (makemigrations, tests) won't fail at import time.
        Returns the IPFS hash on success or None on failure.
        """
        if not self.file_stored_on_ipfs:
            return None

        try:
            from ipfs_storage import InterPlanetaryFileSystemStorage
        except Exception:
            return None

        try:
            storage = InterPlanetaryFileSystemStorage()
            # Save file via the IPFS storage backend. `storage.save` should
            # return a stored name/identifier; behavior depends on backend.
            stored_name = storage.save(self.file_stored_on_ipfs.name, self.file_stored_on_ipfs)
            # Update field to reference stored name if applicable
            self.file_stored_on_ipfs.name = stored_name
            # Try to read ipfs hash attribute if backend exposes it
            ipfs_hash = getattr(storage, 'last_ipfs_hash', None) or getattr(self.file_stored_on_ipfs, 'ipfs_hash', None)
            if ipfs_hash:
                self.ipfs_hash = ipfs_hash
            self.save(update_fields=['file_stored_on_ipfs', 'ipfs_hash'])
            return self.ipfs_hash or stored_name
        except Exception:
            return None