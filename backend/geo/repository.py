"""
UPRN Repository - Database access layer using existing DatabasePool.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

# Deferred import to avoid circular imports and help PyCharm
if TYPE_CHECKING:
    pass

from backend.core.database.db_pool import DatabasePool
from backend.geo.confidence import RawCandidate


class UPRNRepository:
    """Repository for UPRN spatial queries."""

    @staticmethod
    async def get_uprn_candidates(
        postcode: str,
        radius_m: float = 60.0,
        limit: int = 20
    ) -> list[RawCandidate]:
        """
        Get UPRN candidates within radius of postcode centroid.
        Uses PostGIS ST_DWithin for efficient spatial query.
        """
        query = """
        WITH postcode_geom AS (
            SELECT geom 
            FROM postcode_centroids 
            WHERE postcode = $1
        ),
        candidates AS (
            SELECT 
                u.uprn,
                ST_Distance(u.geom, pc.geom) as distance_m
            FROM uprn_points u
            CROSS JOIN postcode_geom pc
            WHERE ST_DWithin(u.geom, pc.geom, $2)
            ORDER BY distance_m
            LIMIT $3
        )
        SELECT 
            c.uprn,
            c.distance_m,
            COALESCE(d.neighbor_count, 1) as neighbor_count
        FROM candidates c
        LEFT JOIN uprn_density_30m d ON c.uprn = d.uprn
        ORDER BY c.distance_m;
        """

        rows = await DatabasePool.fetch(query, postcode, radius_m, limit)

        return [
            RawCandidate(
                uprn=row['uprn'],
                distance_m=float(row['distance_m']),
                neighbor_count=row['neighbor_count']
            )
            for row in rows
        ]

    @staticmethod
    async def postcode_exists(postcode: str) -> bool:
        """Check if postcode exists in our database."""
        query = "SELECT EXISTS(SELECT 1 FROM postcode_centroids WHERE postcode = $1)"
        result = await DatabasePool.fetchval(query, postcode)
        return result

    @staticmethod
    async def get_stats() -> dict:
        """Get database statistics for health check."""
        uprn_count = await DatabasePool.fetchval("SELECT COUNT(*) FROM uprn_points")
        postcode_count = await DatabasePool.fetchval("SELECT COUNT(*) FROM postcode_centroids")

        # Check if density view exists
        view_exists = await DatabasePool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'uprn_density_30m')"
        )
        density_count = 0
        if view_exists:
            density_count = await DatabasePool.fetchval("SELECT COUNT(*) FROM uprn_density_30m")

        return {
            "uprn_count": uprn_count,
            "postcode_count": postcode_count,
            "density_view_count": density_count
        }