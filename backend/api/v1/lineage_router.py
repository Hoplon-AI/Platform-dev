"""
Data lineage visualization endpoints.
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from backend.core.audit.lineage_visualizer import LineageVisualizer

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])
lineage_visualizer = LineageVisualizer()


@router.get("/{ha_id}/submission/{submission_id}")
async def get_submission_lineage(ha_id: str, submission_id: str) -> Dict[str, Any]:
    """
    Get submission-based lineage graph.
    
    Args:
        ha_id: Housing Association ID
        submission_id: Upload UUID
        
    Returns:
        Dictionary with nodes and edges for visualization
    """
    try:
        graph = await lineage_visualizer.build_submission_graph(submission_id, ha_id)
        return graph
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build lineage graph: {str(e)}"
        )


@router.get("/{ha_id}/uprn/{uprn}")
async def get_uprn_lineage(ha_id: str, uprn: str) -> Dict[str, Any]:
    """
    Get UPRN-based lineage graph.
    
    Args:
        ha_id: Housing Association ID
        uprn: Unique Property Reference Number
        
    Returns:
        Dictionary with nodes and edges for visualization
    """
    try:
        graph = await lineage_visualizer.build_uprn_graph(uprn, ha_id)
        return graph
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build UPRN lineage graph: {str(e)}"
        )


@router.get("/{ha_id}/output/{output_id}")
async def get_output_lineage(ha_id: str, output_id: str) -> Dict[str, Any]:
    """
    Get output-to-source lineage trace (backward trace).
    
    Args:
        ha_id: Housing Association ID
        output_id: Output UUID (PDF, report, etc.)
        
    Returns:
        Dictionary with nodes and edges for visualization
    """
    try:
        graph = await lineage_visualizer.build_output_graph(output_id, ha_id)
        return graph
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build output lineage graph: {str(e)}"
        )
