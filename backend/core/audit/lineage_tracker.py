"""
Data lineage tracking (upload → processing → output).
"""
import uuid
import asyncpg
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


@dataclass
class LineageNode:
    """Represents a node in the lineage graph."""
    id: str
    type: str  # 'upload', 'processing', 'property', 'block', 'rating', 'output'
    label: str
    metadata: Dict[str, Any]


@dataclass
class LineageEdge:
    """Represents an edge in the lineage graph."""
    source: str
    target: str
    type: str  # 'transformation', 'calculation', 'generation'
    label: str
    metadata: Optional[Dict[str, Any]] = None


class LineageTracker:
    """Tracks data lineage through transformations."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize lineage tracker.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def create_lineage_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        transformation_type: str,
    ):
        """
        Create a lineage link between source and target.
        
        Args:
            source_type: Source entity type
            source_id: Source entity ID
            target_type: Target entity type
            target_id: Target entity ID
            transformation_type: Type of transformation
        """
        try:
            await self._store_lineage_link(
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                transformation_type=transformation_type,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip operation
            pass
    
    async def get_lineage_forward(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get forward lineage (what was created from this entity).
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            
        Returns:
            List of lineage links with source_id, target_id, target_type, transformation_type
        """
        try:
            records = await self.db_adapter.fetch(
                """
                SELECT 
                    source_type, source_id, target_type, target_id, transformation_type, created_at
                FROM data_lineage
                WHERE source_type = $1 AND source_id = $2
                ORDER BY created_at ASC
                """,
                entity_type,
                uuid.UUID(entity_id),
            )
            
            return [
                {
                    'source_type': record['source_type'],
                    'source_id': str(record['source_id']),
                    'target_type': record['target_type'],
                    'target_id': str(record['target_id']),
                    'transformation_type': record['transformation_type'],
                    'created_at': record['created_at'].isoformat() if record['created_at'] else None,
                }
                for record in records
            ]
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
    
    async def get_lineage_backward(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get backward lineage (what created this entity).
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            
        Returns:
            List of lineage links with source_id, source_type, target_id, transformation_type
        """
        try:
            records = await self.db_adapter.fetch(
                """
                SELECT 
                    source_type, source_id, target_type, target_id, transformation_type, created_at
                FROM data_lineage
                WHERE target_type = $1 AND target_id = $2
                ORDER BY created_at ASC
                """,
                entity_type,
                uuid.UUID(entity_id),
            )
            
            return [
                {
                    'source_type': record['source_type'],
                    'source_id': str(record['source_id']),
                    'target_type': record['target_type'],
                    'target_id': str(record['target_id']),
                    'transformation_type': record['transformation_type'],
                    'created_at': record['created_at'].isoformat() if record['created_at'] else None,
                }
                for record in records
            ]
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return []
    
    async def get_full_lineage(self, entity_type: str, entity_id: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Get full lineage graph (both forward and backward).
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary with 'nodes' and 'edges' lists
        """
        try:
            # Use recursive CTE to build full lineage graph
            # This query finds all connected entities up to max_depth
            query = """
            WITH RECURSIVE lineage_graph AS (
                -- Start with the root entity
                SELECT 
                    source_type, source_id, target_type, target_id, transformation_type, created_at, 0 as depth
                FROM data_lineage
                WHERE (source_type = $1 AND source_id = $2) OR (target_type = $1 AND target_id = $2)
                
                UNION ALL
                
                -- Forward traversal
                SELECT 
                    dl.source_type, dl.source_id, dl.target_type, dl.target_id, 
                    dl.transformation_type, dl.created_at, lg.depth + 1
                FROM data_lineage dl
                INNER JOIN lineage_graph lg ON (
                    dl.source_type = lg.target_type AND dl.source_id = lg.target_id
                )
                WHERE lg.depth < $3
                
                UNION ALL
                
                -- Backward traversal
                SELECT 
                    dl.source_type, dl.source_id, dl.target_type, dl.target_id,
                    dl.transformation_type, dl.created_at, lg.depth + 1
                FROM data_lineage dl
                INNER JOIN lineage_graph lg ON (
                    dl.target_type = lg.source_type AND dl.target_id = lg.source_id
                )
                WHERE lg.depth < $3
            )
            SELECT DISTINCT source_type, source_id, target_type, target_id, transformation_type, created_at
            FROM lineage_graph
            ORDER BY created_at ASC
            """
            
            records = await self.db_adapter.fetch(
                query,
                entity_type,
                uuid.UUID(entity_id),
                max_depth,
            )
            
            # Build nodes and edges
            nodes = {}
            edges = []
            
            # Add root node
            root_id = f"{entity_type}_{entity_id}"
            nodes[root_id] = {
                'id': root_id,
                'type': entity_type,
                'label': f"{entity_type.title()}: {entity_id[:8]}...",
                'metadata': {'entity_id': entity_id, 'entity_type': entity_type},
            }
            
            # Process all links
            for record in records:
                source_id = f"{record['source_type']}_{record['source_id']}"
                target_id = f"{record['target_type']}_{record['target_id']}"
                
                # Add source node
                if source_id not in nodes:
                    nodes[source_id] = {
                        'id': source_id,
                        'type': record['source_type'],
                        'label': f"{record['source_type'].title()}: {str(record['source_id'])[:8]}...",
                        'metadata': {
                            'entity_id': str(record['source_id']),
                            'entity_type': record['source_type'],
                        },
                    }
                
                # Add target node
                if target_id not in nodes:
                    nodes[target_id] = {
                        'id': target_id,
                        'type': record['target_type'],
                        'label': f"{record['target_type'].title()}: {str(record['target_id'])[:8]}...",
                        'metadata': {
                            'entity_id': str(record['target_id']),
                            'entity_type': record['target_type'],
                        },
                    }
                
                # Add edge
                edges.append({
                    'source': source_id,
                    'target': target_id,
                    'type': record['transformation_type'] or 'transformation',
                    'label': record['transformation_type'] or 'transformation',
                    'metadata': {
                        'created_at': record['created_at'].isoformat() if record['created_at'] else None,
                    },
                })
            
            return {
                'nodes': list(nodes.values()),
                'edges': edges,
            }
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available
            return {'nodes': [], 'edges': []}
    
    async def _store_lineage_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        transformation_type: str,
    ):
        """Store lineage link in database."""
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
