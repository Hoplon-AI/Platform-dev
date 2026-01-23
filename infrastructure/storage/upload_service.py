"""
File upload handler with checksum validation for Bronze layer.
"""
import hashlib
import uuid
from typing import BinaryIO, Tuple, Optional, Any, Dict, List
from datetime import datetime
import json
import boto3
from botocore.exceptions import ClientError

from infrastructure.storage.s3_config import get_s3_config


class UploadService:
    """Service for handling file uploads to S3 with integrity checks."""
    
    def __init__(self, s3_config=None):
        """
        Initialize upload service.
        
        Args:
            s3_config: S3Config instance (defaults to global config)
        """
        self.s3_config = s3_config or get_s3_config()
        self.s3_client = self.s3_config.get_client()
        self.bucket_name = self.s3_config.get_bucket_name()
    
    def calculate_checksum(self, file_content: bytes) -> str:
        """
        Calculate SHA-256 checksum for file content.
        
        Args:
            file_content: File content as bytes
            
        Returns:
            SHA-256 hex digest
        """
        return hashlib.sha256(file_content).hexdigest()
    
    def upload_file(
        self,
        ha_id: str,
        file_content: bytes,
        filename: str,
        file_type: str,
        user_id: str,
    ) -> Tuple[str, str, str]:
        """
        Upload file to S3 with checksum validation.
        
        Args:
            ha_id: Housing Association ID
            file_content: File content as bytes
            filename: Original filename
            file_type: File type (e.g., 'property_schedule', 'epc_data', 'fra_document')
            user_id: User ID who uploaded the file
            
        Returns:
            Tuple of (upload_id, s3_key, checksum)
            
        Raises:
            ClientError: If S3 upload fails
        """
        # Generate upload ID
        upload_id = str(uuid.uuid4())
        
        # Calculate checksum
        checksum = self.calculate_checksum(file_content)
        
        # Generate S3 key
        s3_key = self.s3_config.generate_s3_key(ha_id, upload_id, filename, file_type=file_type)
        
        # Ensure bucket exists
        self.s3_config.ensure_bucket_exists()
        
        # Upload to S3
        try:
            uploaded_at = datetime.utcnow().isoformat()
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                Metadata={
                    'upload_id': upload_id,
                    'ha_id': ha_id,
                    'filename': filename,
                    'file_type': file_type,
                    'user_id': user_id,
                    'checksum': checksum,
                    'uploaded_at': uploaded_at,
                },
                ContentType=self._get_content_type(filename),
            )

            # Write submission metadata + manifest alongside the file.
            # These make lineage tracing and debugging trivial without scanning S3 listings.
            submission_prefix = self.s3_config.generate_submission_prefix(
                ha_id=ha_id,
                dataset=file_type,
                submission_id=upload_id,
            )

            metadata_payload = {
                "upload_id": upload_id,
                "ha_id": ha_id,
                "user_id": user_id,
                "file_type": file_type,
                "filename": filename,
                "s3_key": s3_key,
                "checksum": checksum,
                "file_size": len(file_content),
                "uploaded_at": uploaded_at,
            }

            manifest_payload = {
                "submission_id": upload_id,
                "ha_id": ha_id,
                "dataset": file_type,
                "ingested_at": uploaded_at,
                "objects": [
                    {
                        "role": "source",
                        "filename": filename,
                        "s3_key": s3_key,
                        "checksum": checksum,
                        "file_size": len(file_content),
                        "content_type": self._get_content_type(filename),
                    }
                ],
            }

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{submission_prefix}metadata.json",
                Body=json.dumps(metadata_payload, indent=2).encode("utf-8"),
                ContentType="application/json",
            )

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{submission_prefix}manifest.json",
                Body=json.dumps(manifest_payload, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as e:
            raise Exception(f"Failed to upload file to S3: {str(e)}")
        
        return upload_id, s3_key, checksum

    def put_json(self, key: str, payload: Dict[str, Any]) -> None:
        """
        Store a JSON payload in S3 at the given key.
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(payload, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as e:
            raise Exception(f"Failed to write JSON to S3: {str(e)}")

    def get_json(self, key: str) -> Dict[str, Any]:
        """
        Read a JSON payload from S3.
        """
        raw = self.get_file(key)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise Exception(f"Failed to parse JSON from S3 ({key}): {str(e)}")

    def append_manifest_objects(self, manifest_key: str, new_objects: List[Dict[str, Any]]) -> None:
        """
        Append objects to an existing submission manifest.json (best-effort).
        """
        try:
            manifest = self.get_json(manifest_key)
        except Exception:
            # If manifest can't be read, don't block the upload flow.
            return

        objects = manifest.get("objects")
        if not isinstance(objects, list):
            objects = []

        # De-dupe by s3_key if present
        existing_keys = {
            o.get("s3_key") for o in objects if isinstance(o, dict) and o.get("s3_key")
        }
        for obj in new_objects:
            if not isinstance(obj, dict):
                continue
            s3_key = obj.get("s3_key")
            if s3_key and s3_key in existing_keys:
                continue
            objects.append(obj)
            if s3_key:
                existing_keys.add(s3_key)

        manifest["objects"] = objects
        self.put_json(manifest_key, manifest)
    
    def get_file(self, s3_key: str) -> bytes:
        """
        Retrieve file from S3.
        
        Args:
            s3_key: S3 key path
            
        Returns:
            File content as bytes
            
        Raises:
            ClientError: If file retrieval fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return response['Body'].read()
        except ClientError as e:
            raise Exception(f"Failed to retrieve file from S3: {str(e)}")
    
    def verify_checksum(self, s3_key: str, expected_checksum: str) -> bool:
        """
        Verify file checksum matches expected value.
        
        Args:
            s3_key: S3 key path
            expected_checksum: Expected SHA-256 checksum
            
        Returns:
            True if checksum matches, False otherwise
        """
        file_content = self.get_file(s3_key)
        actual_checksum = self.calculate_checksum(file_content)
        return actual_checksum == expected_checksum
    
    def delete_file(self, s3_key: str):
        """
        Delete file from S3.
        
        Args:
            s3_key: S3 key path
            
        Raises:
            ClientError: If file deletion fails
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
        except ClientError as e:
            raise Exception(f"Failed to delete file from S3: {str(e)}")
    
    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type from filename.
        
        Args:
            filename: Filename
            
        Returns:
            MIME content type
        """
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        content_types = {
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel',
            'pdf': 'application/pdf',
            'json': 'application/json',
        }
        return content_types.get(ext, 'application/octet-stream')


# Global upload service instance
_upload_service: Optional[UploadService] = None


def get_upload_service() -> UploadService:
    """Get global upload service instance (singleton)."""
    global _upload_service
    if _upload_service is None:
        _upload_service = UploadService()
    return _upload_service
