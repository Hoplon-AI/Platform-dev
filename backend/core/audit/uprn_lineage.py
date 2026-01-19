"""
UPRN-based data lineage and traceability.
"""
import uuid
import asyncpg
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


class UPRNLineage:
    """Tracks lineage based on UPRN (Unique Property Reference Number)."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize UPRN lineage tracker.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def link_uprn_to_submission(
        self,
        uprn: str,
        ha_id: str,
        submission_id: str,
        property_id: Optional[str] = None,
    ):
        """
        Link a UPRN to a submission.
        
        Args:
            uprn: Unique Property Reference Number (12 digits)
            ha_id: Housing Association ID
            submission_id: Upload UUID
            property_id: Optional property UUID
        """
        try:
            await self._store_uprn_mapping(
                uprn=uprn,
                ha_id=ha_id,
                submission_id=submission_id,
                property_id=property_id,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip operation
            pass
    
    async def get_uprn_lineage(self, uprn: str, ha_id: str) -> Dict[str, Any]:
        """
        Get full lineage for a UPRN (all sources and outputs).
        
        Args:
            uprn: Unique Property Reference Number
            ha_id: Housing Association ID
            
        Returns:
            Dictionary with lineage graph (nodes and edges)
        """
        try:
            # Get all submissions for this UPRN
            submissions = await self.get_submissions_for_uprn(uprn, ha_id)
            
            # Get all properties for this UPRN
            properties = await self.get_properties_for_uprn(uprn, ha_id)
            
            # Build nodes and edges
            nodes = []
            edges = []
            
            # Add UPRN as central node
            nodes.append({
                'id': f"uprn_{uprn}",
                'type': 'uprn',
                'label': f'UPRN: {uprn}',
                'metadata': {'uprn': uprn, 'ha_id': ha_id},
            })
            
            # Add submission nodes and edges
            for submission_id in submissions:
                nodes.append({
                    'id': f"upload_{submission_id}",
                    'type': 'upload',
                    'label': f'Submission: {submission_id[:8]}...',
                    'metadata': {'submission_id': submission_id},
                })
                edges.append({
                    'source': f"upload_{submission_id}",
                    'target': f"uprn_{uprn}",
                    'type': 'contains',
                    'label': 'Contains UPRN',
                })
            
            # Add property nodes and edges
            for property_id in properties:
                nodes.append({
                    'id': f"property_{property_id}",
                    'type': 'property',
                    'label': f'Property: {property_id[:8]}...',
                    'metadata': {'property_id': property_id},
                })
                edges.append({
                    'source': f"uprn_{uprn}",
                    'target': f"property_{property_id}",
                    'type': 'identified_by',
                    'label': 'Identified by UPRN',
                })
            
            return {
                'nodes': nodes,
                'edges': edges,
            }
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return {'nodes': [], 'edges': []}
    
    async def get_submissions_for_uprn(self, uprn: str, ha_id: str) -> List[str]:
        """
        Get all submissions that contain this UPRN.
        
        Args:
            uprn: Unique Property Reference Number
            ha_id: Housing Association ID
            
        Returns:
            List of submission IDs
        """
        try:
            records = await self.db_adapter.fetch(
                """
                SELECT DISTINCT submission_id
                FROM uprn_lineage_map
                WHERE uprn = $1 AND ha_id = $2
                ORDER BY first_seen_at ASC
                """,
                uprn,
                ha_id,
            )
            
            return [str(record['submission_id']) for record in records]
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
    
    async def get_properties_for_uprn(self, uprn: str, ha_id: str) -> List[str]:
        """
        Get all property IDs associated with this UPRN.
        
        Args:
            uprn: Unique Property Reference Number
            ha_id: Housing Association ID
            
        Returns:
            List of property IDs
        """
        try:
            records = await self.db_adapter.fetch(
                """
                SELECT property_id
                FROM properties_silver
                WHERE uprn = $1 AND ha_id = $2
                ORDER BY created_at ASC
                """,
                uprn,
                ha_id,
            )
            
            return [str(record['property_id']) for record in records]
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
    
    async def _store_uprn_mapping(
        self,
        uprn: str,
        ha_id: str,
        submission_id: str,
        property_id: Optional[str] = None,
    ):
        """Store UPRN mapping in database."""
        # Use INSERT ... ON CONFLICT to update last_updated_at if record exists
        await self.db_adapter.execute(
            """
            INSERT INTO uprn_lineage_map (
                uprn, ha_id, submission_id, property_id, first_seen_at, last_updated_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (uprn, ha_id, submission_id) 
            DO UPDATE SET 
                property_id = COALESCE(EXCLUDED.property_id, uprn_lineage_map.property_id),
                last_updated_at = NOW()
            """,
            uprn,
            ha_id,
            uuid.UUID(submission_id),
            uuid.UUID(property_id) if property_id else None,
        )
