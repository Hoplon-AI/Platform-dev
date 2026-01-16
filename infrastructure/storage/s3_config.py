"""
S3 client configuration and bucket management for Bronze layer storage.
"""
import os
import boto3
from botocore.config import Config
from typing import Optional
from functools import lru_cache


class S3Config:
    """S3 configuration and client management."""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        """
        Initialize S3 configuration.
        
        Args:
            bucket_name: S3 bucket name (defaults to env var or 'platform-bronze')
            region: AWS region
            endpoint_url: Custom endpoint URL (for localstack/testing)
            access_key_id: AWS access key (defaults to env var)
            secret_access_key: AWS secret key (defaults to env var)
        """
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME", "platform-bronze")
        self.region = region
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        
        # AWS credentials from environment or parameters
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # S3 client configuration
        self.config = Config(
            region_name=self.region,
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
    
    @lru_cache(maxsize=1)
    def get_client(self):
        """
        Get or create S3 client (cached).
        
        Returns:
            boto3 S3 client
        """
        client_kwargs = {
            'config': self.config,
        }
        
        if self.endpoint_url:
            client_kwargs['endpoint_url'] = self.endpoint_url
        
        if self.access_key_id and self.secret_access_key:
            client_kwargs['aws_access_key_id'] = self.access_key_id
            client_kwargs['aws_secret_access_key'] = self.secret_access_key
        
        return boto3.client('s3', **client_kwargs)
    
    def ensure_bucket_exists(self):
        """
        Ensure the S3 bucket exists, create if it doesn't.
        
        Raises:
            ClientError: If bucket creation fails
        """
        client = self.get_client()
        
        try:
            client.head_bucket(Bucket=self.bucket_name)
        except client.exceptions.NoSuchBucket:
            # Create bucket if it doesn't exist
            create_kwargs = {'Bucket': self.bucket_name}
            if self.region != 'us-east-1':
                create_kwargs['CreateBucketConfiguration'] = {
                    'LocationConstraint': self.region
                }
            client.create_bucket(**create_kwargs)
    
    def get_bucket_name(self) -> str:
        """Get the configured bucket name."""
        return self.bucket_name
    
    def generate_s3_key(self, ha_id: str, upload_id: str, filename: str) -> str:
        """
        Generate S3 key for upload following structure: {ha_id}/bronze/{upload_id}/{filename}
        
        Args:
            ha_id: Housing Association ID
            upload_id: Upload UUID
            filename: Original filename
            
        Returns:
            S3 key path
        """
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(filename).replace('..', '').replace('/', '_')
        return f"{ha_id}/bronze/{upload_id}/{safe_filename}"


# Global S3 config instance
_s3_config: Optional[S3Config] = None


def get_s3_config() -> S3Config:
    """Get global S3 config instance (singleton)."""
    global _s3_config
    if _s3_config is None:
        _s3_config = S3Config()
    return _s3_config


def set_s3_config(config: S3Config):
    """Set global S3 config instance (for testing)."""
    global _s3_config
    _s3_config = config
