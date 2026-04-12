"""
Centralized audit logging service for all data operations.
"""
import uuid
import json
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


class AuditEventType(Enum):
    """Types of audit events."""
    UPLOAD = "upload"
    PROCESSING = "processing"
    TRANSFORMATION = "transformation"
    OUTPUT = "output"
    DELETION = "deletion"
    ACCESS = "access"
    CONFIG_CHANGE = "config_change"

class AuditLogger:
    """Centralized audit logging service."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize audit logger.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def log_upload(
        self,
        upload_id: str,
        ha_id: str,
        file_type: str,
        filename: str,
        s3_key: str,
        checksum: str,
        file_size: int,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        stepfn_execution_arn: Optional[str] = None,
    ):
        """
        Log file upload event.
        
        Args:
            upload_id: Upload UUID
            ha_id: Housing Association ID
            file_type: File type
            filename: Original filename
            s3_key: S3 key path
            checksum: SHA-256 checksum
            file_size: File size in bytes
            user_id: User ID who uploaded
            metadata: Additional metadata
        """
        try:
            await self._store_upload_audit(
                upload_id=upload_id,
                ha_id=ha_id,
                file_type=file_type,
                filename=filename,
                s3_key=s3_key,
                checksum=checksum,
                file_size=file_size,
                user_id=user_id,
                metadata=metadata,
                status=status,
                stepfn_execution_arn=stepfn_execution_arn,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip logging
            pass
    
    async def log_processing(
        self,
        processing_id: str,
        ha_id: str,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        transformation_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log data processing/transformation event.
        
        Args:
            processing_id: Processing UUID
            ha_id: Housing Association ID
            source_type: Source entity type ('upload', 'processing', 'property')
            source_id: Source entity ID
            target_type: Target entity type
            target_id: Target entity ID
            transformation_type: Type of transformation
            metadata: Additional metadata
        """
        try:
            # Store in processing_audit table
            await self._store_processing_audit(
                processing_id=processing_id,
                ha_id=ha_id,
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                transformation_type=transformation_type,
                metadata=metadata,
            )
            
            # Also create lineage link
            await self._create_lineage_link(
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                transformation_type=transformation_type,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip logging
            pass
    
    async def log_output(
        self,
        output_id: str,
        ha_id: str,
        output_type: str,
        source_ids: list,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log output generation event (PDF, report, etc.).
        
        Args:
            output_id: Output UUID
            ha_id: Housing Association ID
            output_type: Type of output ('pdf', 'report', etc.)
            source_ids: List of source entity IDs
            metadata: Additional metadata
        """
        try:
            # Store in output_audit table
            await self._store_output_audit(
                output_id=output_id,
                ha_id=ha_id,
                output_type=output_type,
                source_ids=source_ids,
                metadata=metadata,
            )
            
            # Create lineage links to all sources
            for source_id in source_ids:
                await self._create_lineage_link(
                    source_type='processing',
                    source_id=source_id,
                    target_type='output',
                    target_id=output_id,
                    transformation_type='generation',
                )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip logging
            pass
    
    async def log_deletion(
        self,
        deletion_id: str,
        ha_id: str,
        deletion_type: str,
        entity_type: str,
        entity_id: str,
        deleted_by: str,
        deletion_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log data deletion event (GDPR compliance).
        
        Args:
            deletion_id: Deletion UUID
            ha_id: Housing Association ID
            deletion_type: Type of deletion ('gdpr_request', 'retention_policy', 'manual')
            entity_type: Type of entity deleted
            entity_id: Entity ID
            deleted_by: User who performed deletion
            deletion_reason: Reason for deletion
            metadata: Additional metadata (what was deleted)
        """
        try:
            await self._store_deletion_audit(
                deletion_id=deletion_id,
                ha_id=ha_id,
                deletion_type=deletion_type,
                entity_type=entity_type,
                entity_id=entity_id,
                deleted_by=deleted_by,
                deletion_reason=deletion_reason,
                metadata=metadata,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip logging
            pass
    
    async def _store_upload_audit(
        self,
        upload_id: str,
        ha_id: str,
        file_type: str,
        filename: str,
        s3_key: str,
        checksum: str,
        file_size: int,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        stepfn_execution_arn: Optional[str] = None,
    ):
        """Store upload audit record in database."""
        await self.db_adapter.execute(
    """
    INSERT INTO upload_audit (
        upload_id, ha_id, file_type, filename, s3_key,
        checksum, file_size, user_id, status, metadata, stepfn_execution_arn
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    """,
    str(upload_id),
    ha_id,
    file_type,
    filename,
    s3_key,
    checksum,
    file_size,
    user_id,
    status,
    json.dumps(metadata) if metadata else None,
    stepfn_execution_arn,
)
    
    async def _store_processing_audit(
        self,
        processing_id: str,
        ha_id: str,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        transformation_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Store processing audit record in database."""
        await self.db_adapter.execute(
            """
            INSERT INTO processing_audit (
                processing_id, ha_id, source_type, source_id,
                target_type, target_id, transformation_type,
                status, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(processing_id),
            ha_id,
            source_type,
            uuid.UUID(source_id),
            target_type,
            uuid.UUID(target_id),
            transformation_type,
            'pending',
            json.dumps(metadata) if metadata else None,
        )
    
    async def _store_output_audit(
        self,
        output_id: str,
        ha_id: str,
        output_type: str,
        source_ids: list,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Store output audit record in database."""
        # Convert source_ids to JSON array
        source_ids_json = json.dumps(source_ids)
        
        await self.db_adapter.execute(
            """
            INSERT INTO output_audit (
                output_id, ha_id, output_type, source_ids, metadata
            )
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            uuid.UUID(output_id),
            ha_id,
            output_type,
            source_ids_json,
            json.dumps(metadata) if metadata else None,
        )
    
    async def _store_deletion_audit(
        self,
        deletion_id: str,
        ha_id: str,
        deletion_type: str,
        entity_type: str,
        entity_id: str,
        deleted_by: str,
        deletion_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Store deletion audit record in database."""
        await self.db_adapter.execute(
            """
            INSERT INTO deletion_audit (
                deletion_id, ha_id, deletion_type, entity_type,
                entity_id, deleted_by, deletion_reason, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            uuid.UUID(deletion_id),
            ha_id,
            deletion_type,
            entity_type,
            entity_id,
            deleted_by,
            deletion_reason,
            json.dumps(metadata) if metadata else None,
        )
    
    async def _create_lineage_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        transformation_type: str,
    ):
        """Create lineage link in data_lineage table."""
        # Check if link already exists to avoid duplicates
        existing = await self.db_adapter.fetchval(
            """
            SELECT lineage_id FROM data_lineage
            WHERE source_type = $1 AND source_id = $2
            AND target_type = $3 AND target_id = $4
            """,
            source_type,
            uuid.UUID(source_id),
            target_type,
            uuid.UUID(target_id),
        )
        
        if existing is None:
            await self.db_adapter.execute(
                """
                INSERT INTO data_lineage (
                    source_type, source_id, target_type, target_id, transformation_type
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                source_type,
                uuid.UUID(source_id),
                target_type,
                uuid.UUID(target_id),
                transformation_type,
            )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance (singleton)."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
