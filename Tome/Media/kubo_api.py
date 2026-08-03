from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import BinaryIO

from django.conf import settings
import httpx


@dataclass(frozen=True)
class KuboUploadResult:
    """Structured result returned by Kubo `/api/v0/add`."""

    name: str
    cid: str
    size: int


class KuboAPIUploader:
    """Small client object for uploading content to a Kubo node."""

    def __init__(self, api_base_url: str | None = None, timeout: float = 30.0):
        default_url = getattr(settings, "IPFS_STORAGE_API_URL", "http://127.0.0.1:5001/api/v0/")
        self.api_base_url = (api_base_url or default_url).rstrip("/") + "/"
        self.timeout = timeout

    def upload_path(
        self,
        file_path: str,
        *,
        pin: bool = True,
        wrap_with_directory: bool = False,
        cid_version: int | None = None,
        hash_algorithm: str | None = None,
    ) -> KuboUploadResult:
        """Upload a local file path to Kubo and return the resulting CID."""
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as file_obj:
            return self.upload_fileobj(
                file_obj,
                file_name=filename,
                pin=pin,
                wrap_with_directory=wrap_with_directory,
                cid_version=cid_version,
                hash_algorithm=hash_algorithm,
            )

    def upload_bytes(
        self,
        data: bytes,
        *,
        file_name: str,
        pin: bool = True,
        wrap_with_directory: bool = False,
        cid_version: int | None = None,
        hash_algorithm: str | None = None,
    ) -> KuboUploadResult:
        """Upload raw bytes with a provided virtual file name."""
        return self.upload_fileobj(
            io.BytesIO(data),
            file_name=file_name,
            pin=pin,
            wrap_with_directory=wrap_with_directory,
            cid_version=cid_version,
            hash_algorithm=hash_algorithm,
        )

    def upload_fileobj(
        self,
        file_obj: BinaryIO,
        *,
        file_name: str,
        pin: bool = True,
        wrap_with_directory: bool = False,
        cid_version: int | None = None,
        hash_algorithm: str | None = None,
    ) -> KuboUploadResult:
        """Upload any binary file-like object supported by IPFS/Kubo."""
        params = {
            "pin": str(pin).lower(),
            "wrap-with-directory": str(wrap_with_directory).lower(),
        }

        if cid_version is not None:
            params["cid-version"] = str(cid_version)
        if hash_algorithm:
            params["hash"] = hash_algorithm

        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        files = {"file": (file_name, file_obj, "application/octet-stream")}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.api_base_url}add", params=params, files=files)
            response.raise_for_status()

        # Kubo may stream multiple JSON lines. The last line is the final object.
        payload = self._parse_add_response(response.text)

        cid = payload.get("Hash")
        name = payload.get("Name", file_name)
        size_raw = payload.get("Size", 0)

        if not cid:
            raise ValueError(f"Kubo add response is missing Hash: {payload}")

        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = 0

        return KuboUploadResult(name=name, cid=cid, size=size)

    @staticmethod
    def _parse_add_response(response_text: str) -> dict:
        """Parse Kubo newline-delimited JSON output from `/api/v0/add`."""
        lines = [line.strip() for line in response_text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Kubo add response was empty")

        for line in reversed(lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Unable to parse Kubo add response: {response_text}")
