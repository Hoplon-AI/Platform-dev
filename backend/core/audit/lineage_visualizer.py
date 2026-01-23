"""
Graph structure builder for lineage visualization.
"""
import uuid
import json
import asyncpg
from typing import List, Dict, Any, Optional
from backend.core.audit.lineage_tracker import LineageNode, LineageEdge
from backend.core.audit.submission_lineage import SubmissionLineage
from backend.core.audit.uprn_lineage import UPRNLineage
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)


class LineageVisualizer:
    """Builds graph structures for frontend lineage visualization."""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize lineage visualizer.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
        
        self.submission_lineage = SubmissionLineage(db_pool)
        self.uprn_lineage = UPRNLineage(db_pool)
    
    async def build_submission_graph(self, submission_id: str, ha_id: str) -> Dict[str, Any]:
        """
        Build graph structure for submission-based lineage.
        
        Args:
            submission_id: Upload UUID
            ha_id: Housing Association ID
            
        Returns:
            Dictionary with 'nodes' and 'edges' lists for visualization
        """
        # Get lineage data
        lineage_data = await self.submission_lineage.get_submission_lineage(submission_id)
        
        # Build nodes and edges
        nodes = []
        edges = []
        
        # Add upload node with actual file metadata
        upload_metadata = await self._get_upload_metadata(submission_id, ha_id)
        nodes.append({
            'id': f"upload_{submission_id}",
            'type': 'upload',
            'label': upload_metadata.get('filename', 'Upload'),
            'metadata': upload_metadata,
        })
        
        # Add processing nodes and edges
        # This is a placeholder - will be populated from actual lineage data
        nodes.append({
            'id': f"property_{submission_id}",
            'type': 'property',
            'label': 'Property Data (Silver)',
            'metadata': {},
        })
        
        edges.append({
            'source': f"upload_{submission_id}",
            'target': f"property_{submission_id}",
            'type': 'transformation',
            'label': 'Validation & Normalization',
        })
        
        return {
            'nodes': nodes,
            'edges': edges,
        }
    
    async def build_uprn_graph(self, uprn: str, ha_id: str) -> Dict[str, Any]:
        """
        Build graph structure for UPRN-based lineage.
        
        Args:
            uprn: Unique Property Reference Number
            ha_id: Housing Association ID
            
        Returns:
            Dictionary with 'nodes' and 'edges' lists for visualization
        """
        # Get lineage data
        lineage_data = await self.uprn_lineage.get_uprn_lineage(uprn, ha_id)
        
        # Build nodes and edges
        nodes = []
        edges = []
        
        # Add UPRN as central node
        nodes.append({
            'id': f"uprn_{uprn}",
            'type': 'uprn',
            'label': f'UPRN: {uprn}',
            'metadata': {'uprn': uprn},
        })
        
        # Add all related submissions with actual file metadata
        submission_ids = await self.uprn_lineage.get_submissions_for_uprn(uprn, ha_id)
        for submission_id in submission_ids:
            upload_metadata = await self._get_upload_metadata(submission_id, ha_id)
            nodes.append({
                'id': f"upload_{submission_id}",
                'type': 'upload',
                'label': upload_metadata.get('filename', 'Submission'),
                'metadata': upload_metadata,
            })
            edges.append({
                'source': f"upload_{submission_id}",
                'target': f"uprn_{uprn}",
                'type': 'contains',
                'label': 'Contains UPRN',
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
        }
    
    async def build_output_graph(self, output_id: str, ha_id: str) -> Dict[str, Any]:
        """
        Build graph structure for output-based lineage (backward trace).
        
        Args:
            output_id: Output UUID (PDF, report, etc.)
            ha_id: Housing Association ID
            
        Returns:
            Dictionary with 'nodes' and 'edges' lists for visualization
        """
        # Get backward lineage
        # This is a placeholder
        nodes = []
        edges = []
        
        # Add output node
        nodes.append({
            'id': f"output_{output_id}",
            'type': 'output',
            'label': 'Insurer-Ready PDF',
            'metadata': {'output_id': output_id},
        })
        
        return {
            'nodes': nodes,
            'edges': edges,
        }
    
    async def _get_upload_metadata(self, upload_id: str, ha_id: str) -> Dict[str, Any]:
        """
        Get upload metadata for node by querying upload_audit table.
        
        Args:
            upload_id: Upload UUID
            ha_id: Housing Association ID (for tenant isolation)
            
        Returns:
            Dictionary with upload metadata including filename, s3_key, etc.
        """
        try:
            record = await self.db_adapter.fetchrow(
                """
                SELECT 
                    upload_id, filename, s3_key, file_type, file_size,
                    checksum, uploaded_at, user_id, status, metadata
                FROM upload_audit
                WHERE upload_id = $1 AND ha_id = $2
                """,
                uuid.UUID(upload_id),
                ha_id,
            )
            
            if record:
                # Parse metadata JSON if present
                metadata_json = record.get('metadata')
                parsed_metadata = {}
                if metadata_json:
                    if isinstance(metadata_json, str):
                        parsed_metadata = json.loads(metadata_json)
                    else:
                        parsed_metadata = metadata_json
                
                return {
                    'upload_id': str(record['upload_id']),
                    'filename': record['filename'],
                    's3_key': record['s3_key'],
                    'file_type': record['file_type'],
                    'file_size': record['file_size'],
                    'checksum': record['checksum'],
                    'uploaded_at': record['uploaded_at'].isoformat() if record['uploaded_at'] else None,
                    'user_id': record['user_id'],
                    'status': record['status'],
                    'metadata': parsed_metadata,
                }
            
            # Return minimal metadata if not found (shouldn't happen, but handle gracefully)
            return {
                'upload_id': upload_id,
                'filename': 'Unknown',
                'status': 'not_found',
            }
        except (RuntimeError, AttributeError) as e:
            # Database pool not initialized or adapter not available
            return {
                'upload_id': upload_id,
                'filename': 'Unknown',
                'status': 'database_error',
                'error': str(e),
            }
        except Exception as e:
            # Other errors (e.g., invalid UUID format)
            return {
                'upload_id': upload_id,
                'filename': 'Unknown',
                'status': 'error',
                'error': str(e),
            }
