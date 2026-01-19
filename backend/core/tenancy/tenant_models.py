"""
Housing Association data models.
"""
import json
import asyncpg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


@dataclass
class HousingAssociation:
    """Housing Association model."""
    ha_id: str
    name: str
    created_at: datetime
    metadata: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'ha_id': self.ha_id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata or {},
        }


class TenantModels:
    """Housing Association data access."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize tenant models.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def get_housing_association(self, ha_id: str) -> Optional[HousingAssociation]:
        """
        Get housing association by ID.
        
        Args:
            ha_id: Housing Association ID
            
        Returns:
            HousingAssociation or None if not found
        """
        try:
            record = await self.db_adapter.fetchrow(
                """
                SELECT ha_id, name, created_at, metadata
                FROM housing_associations
                WHERE ha_id = $1
                """,
                ha_id,
            )
            
            if record:
                # Parse metadata JSON if present
                metadata_dict = None
                if record.get('metadata'):
                    metadata_json = record['metadata']
                    if isinstance(metadata_json, str):
                        metadata_dict = json.loads(metadata_json)
                    else:
                        metadata_dict = metadata_json
                
                return HousingAssociation(
                    ha_id=record['ha_id'],
                    name=record['name'],
                    created_at=record['created_at'],
                    metadata=metadata_dict,
                )
            
            return None
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return None
        except Exception:
            # Other errors (e.g., invalid query)
            return None
    
    async def create_housing_association(
        self,
        ha_id: str,
        name: str,
        metadata: Optional[dict] = None,
    ) -> HousingAssociation:
        """
        Create a new housing association.
        
        Args:
            ha_id: Housing Association ID
            name: Association name
            metadata: Additional metadata
            
        Returns:
            HousingAssociation instance
            
        Raises:
            ValueError: If HA with same ha_id already exists
        """
        ha = HousingAssociation(
            ha_id=ha_id,
            name=name,
            created_at=datetime.utcnow(),
            metadata=metadata,
        )
        
        try:
            # Store in database
            metadata_json = json.dumps(metadata) if metadata else None
            
            await self.db_adapter.execute(
                """
                INSERT INTO housing_associations (ha_id, name, created_at, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                ha_id,
                name,
                ha.created_at,
                metadata_json,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip storage
            pass
        except asyncpg.UniqueViolationError:
            # Unique constraint violation - HA already exists
            raise ValueError(f"Housing Association with ha_id '{ha_id}' already exists")
        except Exception as e:
            # Check error message as fallback for other database errors
            error_msg = str(e).lower()
            if 'unique' in error_msg or 'duplicate' in error_msg or 'already exists' in error_msg:
                raise ValueError(f"Housing Association with ha_id '{ha_id}' already exists")
            raise
        
        return ha
    
    async def list_housing_associations(self) -> List[HousingAssociation]:
        """
        List all housing associations.
        
        Returns:
            List of HousingAssociation instances
        """
        try:
            records = await self.db_adapter.fetch(
                """
                SELECT ha_id, name, created_at, metadata
                FROM housing_associations
                ORDER BY created_at ASC
                """
            )
            
            associations = []
            for record in records:
                # Parse metadata JSON if present
                metadata_dict = None
                if record.get('metadata'):
                    metadata_json = record['metadata']
                    if isinstance(metadata_json, str):
                        metadata_dict = json.loads(metadata_json)
                    else:
                        metadata_dict = metadata_json
                
                associations.append(HousingAssociation(
                    ha_id=record['ha_id'],
                    name=record['name'],
                    created_at=record['created_at'],
                    metadata=metadata_dict,
                ))
            
            return associations
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
        except Exception:
            # Other errors
            return []
