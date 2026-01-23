"""
Upload versioning and metadata tracking for Bronze layer.
"""
import uuid
import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


@dataclass
class UploadVersion:
    """Upload version metadata."""
    upload_id: str
    ha_id: str
    file_type: str
    filename: str
    s3_key: str
    checksum: str
    file_size: int
    user_id: str
    uploaded_at: datetime
    status: str  # 'pending', 'processing', 'completed', 'failed'
    version: int = 1
    parent_upload_id: Optional[str] = None  # For versioned uploads
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['uploaded_at'] = self.uploaded_at.isoformat()
        return data


class VersionManager:
    """Manages upload versioning and metadata."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize version manager.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def create_upload_version(
        self,
        ha_id: str,
        file_type: str,
        filename: str,
        s3_key: str,
        checksum: str,
        file_size: int,
        user_id: str,
        parent_upload_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UploadVersion:
        """
        Create a new upload version record.
        
        Args:
            ha_id: Housing Association ID
            file_type: File type
            filename: Original filename
            s3_key: S3 key path
            checksum: SHA-256 checksum
            file_size: File size in bytes
            user_id: User ID
            parent_upload_id: Parent upload ID for versioned uploads
            metadata: Additional metadata
            
        Returns:
            UploadVersion instance
        """
        upload_id = str(uuid.uuid4())
        
        # Determine version number
        version = 1
        try:
            if parent_upload_id:
                # Get latest version of parent upload
                latest_version = await self.get_latest_version(parent_upload_id)
                if latest_version:
                    version = latest_version.version + 1
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - use version 1
            pass
        
        upload_version = UploadVersion(
            upload_id=upload_id,
            ha_id=ha_id,
            file_type=file_type,
            filename=filename,
            s3_key=s3_key,
            checksum=checksum,
            file_size=file_size,
            user_id=user_id,
            uploaded_at=datetime.utcnow(),
            status='pending',
            version=version,
            parent_upload_id=parent_upload_id,
            metadata=metadata or {},
        )
        
        # Store in database
        try:
            await self._store_in_db(upload_version)
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip storage
            pass
        
        return upload_version
    
    async def get_upload_version(self, upload_id: str) -> Optional[UploadVersion]:
        """
        Get upload version by ID.
        
        Args:
            upload_id: Upload UUID
            
        Returns:
            UploadVersion or None if not found
        """
        try:
            record = await self.db_adapter.fetchrow(
                """
                SELECT 
                    upload_id, ha_id, file_type, filename, s3_key,
                    checksum, file_size, user_id, uploaded_at, status, metadata
                FROM upload_audit
                WHERE upload_id = $1
                """,
                uuid.UUID(upload_id)
            )
            
            if record is None:
                return None
            
            # Extract version from metadata or default to 1
            metadata = json.loads(record['metadata']) if record['metadata'] else {}
            version = metadata.get('version', 1)
            parent_upload_id = metadata.get('parent_upload_id')
            
            return UploadVersion(
                upload_id=str(record['upload_id']),
                ha_id=record['ha_id'],
                file_type=record['file_type'],
                filename=record['filename'],
                s3_key=record['s3_key'],
                checksum=record['checksum'],
                file_size=record['file_size'],
                user_id=record['user_id'],
                uploaded_at=record['uploaded_at'],
                status=record['status'],
                version=version,
                parent_upload_id=parent_upload_id,
                metadata=metadata,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return None
    
    async def get_latest_version(self, parent_upload_id: str) -> Optional[UploadVersion]:
        """
        Get latest version of an upload.
        
        Args:
            parent_upload_id: Parent upload ID
            
        Returns:
            Latest UploadVersion or None
        """
        try:
            # Get all versions with this parent_upload_id, ordered by version desc
            records = await self.db_adapter.fetch(
                """
                SELECT 
                    upload_id, ha_id, file_type, filename, s3_key,
                    checksum, file_size, user_id, uploaded_at, status, metadata
                FROM upload_audit
                WHERE metadata->>'parent_upload_id' = $1
                ORDER BY (metadata->>'version')::int DESC
                LIMIT 1
                """,
                parent_upload_id
            )
            
            if not records:
                return None
            
            record = records[0]
            metadata = json.loads(record['metadata']) if record['metadata'] else {}
            version = metadata.get('version', 1)
            
            return UploadVersion(
                upload_id=str(record['upload_id']),
                ha_id=record['ha_id'],
                file_type=record['file_type'],
                filename=record['filename'],
                s3_key=record['s3_key'],
                checksum=record['checksum'],
                file_size=record['file_size'],
                user_id=record['user_id'],
                uploaded_at=record['uploaded_at'],
                status=record['status'],
                version=version,
                parent_upload_id=parent_upload_id,
                metadata=metadata,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return None
    
    async def get_upload_versions(self, ha_id: str, filename: Optional[str] = None) -> List[UploadVersion]:
        """
        Get all upload versions for an HA, optionally filtered by filename.
        
        Args:
            ha_id: Housing Association ID
            filename: Optional filename filter
            
        Returns:
            List of UploadVersion instances
        """
        try:
            if filename:
                records = await self.db_adapter.fetch(
                    """
                    SELECT 
                        upload_id, ha_id, file_type, filename, s3_key,
                        checksum, file_size, user_id, uploaded_at, status, metadata
                    FROM upload_audit
                    WHERE ha_id = $1 AND filename = $2
                    ORDER BY uploaded_at DESC
                    """,
                    ha_id,
                    filename
                )
            else:
                records = await self.db_adapter.fetch(
                    """
                    SELECT 
                        upload_id, ha_id, file_type, filename, s3_key,
                        checksum, file_size, user_id, uploaded_at, status, metadata
                    FROM upload_audit
                    WHERE ha_id = $1
                    ORDER BY uploaded_at DESC
                    """,
                    ha_id
                )
            
            versions = []
            for record in records:
                metadata = json.loads(record['metadata']) if record['metadata'] else {}
                version = metadata.get('version', 1)
                parent_upload_id = metadata.get('parent_upload_id')
                
                versions.append(UploadVersion(
                    upload_id=str(record['upload_id']),
                    ha_id=record['ha_id'],
                    file_type=record['file_type'],
                    filename=record['filename'],
                    s3_key=record['s3_key'],
                    checksum=record['checksum'],
                    file_size=record['file_size'],
                    user_id=record['user_id'],
                    uploaded_at=record['uploaded_at'],
                    status=record['status'],
                    version=version,
                    parent_upload_id=parent_upload_id,
                    metadata=metadata,
                ))
            
            return versions
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
    
    async def update_upload_status(self, upload_id: str, status: str):
        """
        Update upload status.
        
        Args:
            upload_id: Upload UUID
            status: New status ('pending', 'processing', 'completed', 'failed')
        """
        try:
            await self.db_adapter.execute(
                """
                UPDATE upload_audit
                SET status = $1
                WHERE upload_id = $2
                """,
                status,
                uuid.UUID(upload_id)
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip update
            pass
    
    async def _store_in_db(self, upload_version: UploadVersion):
        """
        Store upload version in database.
        
        Args:
            upload_version: UploadVersion instance
        """
        # Prepare metadata with version and parent info
        metadata = upload_version.metadata.copy() if upload_version.metadata else {}
        metadata['version'] = upload_version.version
        if upload_version.parent_upload_id:
            metadata['parent_upload_id'] = upload_version.parent_upload_id
        
        await self.db_adapter.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key,
                checksum, file_size, user_id, status, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            uuid.UUID(upload_version.upload_id),
            upload_version.ha_id,
            upload_version.file_type,
            upload_version.filename,
            upload_version.s3_key,
            upload_version.checksum,
            upload_version.file_size,
            upload_version.user_id,
            upload_version.status,
            json.dumps(metadata),
        )
