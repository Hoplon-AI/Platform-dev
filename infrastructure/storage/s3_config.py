"""
S3 client configuration and bucket management for Bronze layer storage.
"""
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional
from functools import lru_cache
from datetime import datetime, timezone


class S3Config:
    """S3 configuration and client management."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: str = None,
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
        self.region = region or os.getenv("AWS_REGION", "eu-west-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")

        # AWS credentials: only use explicit credentials for local/test environments.
        # In Lambda (when AWS_LAMBDA_FUNCTION_NAME is set), use IAM role credentials.
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.access_key_id = None
            self.secret_access_key = None
        else:
            self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
            self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        self.config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "standard"},
        )

    @lru_cache(maxsize=1)
    def get_client(self):
        """
        Get or create S3 client (cached).

        Returns:
            boto3 S3 client
        """
        client_kwargs = {
            "config": self.config,
        }

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        return boto3.client("s3", **client_kwargs)

    def ensure_bucket_exists(self):
        """
        Ensure the S3 bucket exists, create if it doesn't.

        Raises:
            ClientError: If bucket creation fails for reasons other than missing bucket
        """
        client = self.get_client()

        try:
            client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

            if error_code in {"404", "NoSuchBucket", "NotFound"} or status_code == 404:
                create_kwargs = {"Bucket": self.bucket_name}
                if self.region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": self.region
                    }
                client.create_bucket(**create_kwargs)
            else:
                raise

    def get_bucket_name(self) -> str:
        """Get the configured bucket name."""
        return self.bucket_name

    def generate_submission_prefix(
        self,
        ha_id: str,
        dataset: str,
        submission_id: str,
        ingest_date: Optional[str] = None,
    ) -> str:
        """
        Generate an S3 prefix for a submission using lake-style partitioning.

        Structure:
          ha_id=<ha_id>/bronze/dataset=<dataset>/ingest_date=<YYYY-MM-DD>/submission_id=<uuid>/
        """
        date_str = ingest_date or datetime.now(timezone.utc).date().isoformat()
        return (
            f"ha_id={ha_id}/bronze/"
            f"dataset={dataset}/ingest_date={date_str}/submission_id={submission_id}/"
        )

    def generate_s3_key(self, ha_id: str, upload_id: str, filename: str, file_type: str) -> str:
        """
        Generate S3 key for Bronze upload using lake-style partitioning.

        Structure:
          ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=<YYYY-MM-DD>/submission_id=<upload_id>/file=<filename>

        Args:
            ha_id: Housing Association ID
            upload_id: Upload UUID
            filename: Original filename
            file_type: Dataset/file type (e.g. property_schedule, epc_data, fra_document)

        Returns:
            S3 key path
        """
        safe_filename = os.path.basename(filename).replace("..", "").replace("/", "_")
        prefix = self.generate_submission_prefix(
            ha_id=ha_id,
            dataset=file_type,
            submission_id=upload_id,
        )
        return f"{prefix}file={safe_filename}"


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