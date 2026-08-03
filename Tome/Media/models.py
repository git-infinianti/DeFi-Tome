from django.db import models
from django.contrib.auth.models import User
from .kubo_api import KuboAPIUploader

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
        """Upload the current file to Kubo `/api/v0/add` and save the CID.

        Returns the resulting CID on success or None on failure.
        """
        if not self.file_stored_on_ipfs:
            return None

        try:
            uploader = KuboAPIUploader()
            result = uploader.upload_fileobj(
                self.file_stored_on_ipfs.file,
                file_name=self.file_stored_on_ipfs.name,
                pin=True,
            )
            self.ipfs_hash = result.cid
            self.save(update_fields=['file_stored_on_ipfs', 'ipfs_hash'])
            return self.ipfs_hash
        except Exception:
            return None