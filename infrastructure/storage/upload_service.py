"""
File upload handler with checksum validation for Bronze layer.
"""
import hashlib
import uuid
from typing import BinaryIO, Tuple, Optional
from datetime import datetime
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
            file_type: File type (e.g., 'property_schedule', 'epc_data', 'frsa_document')
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
        s3_key = self.s3_config.generate_s3_key(ha_id, upload_id, filename)
        
        # Ensure bucket exists
        self.s3_config.ensure_bucket_exists()
        
        # Upload to S3
        try:
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
                    'uploaded_at': datetime.utcnow().isoformat(),
                },
                ContentType=self._get_content_type(filename),
            )
        except ClientError as e:
            raise Exception(f"Failed to upload file to S3: {str(e)}")
        
        return upload_id, s3_key, checksum
    
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
