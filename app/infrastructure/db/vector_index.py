"""Vector index management utilities for pgvector."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


@dataclass
class VectorIndexStats:
    """Statistics for a vector index."""

    index_name: str
    table_name: str
    column_name: str
    index_type: str
    lists: int | None
    probes: int | None
    size_bytes: int
    size_pretty: str
    tuple_count: int
    pages: int


async def create_vector_index(
    session: AsyncSession,
    table_name: str = "memory_records",
    column_name: str = "embedding",
    index_name: str = "ix_memory_records_embedding",
    lists: int = 100,
    index_type: str = "ivfflat",
    operator_class: str = "vector_cosine_ops",
) -> bool:
    """Create a vector index for similarity search.

    Args:
        session: Database session
        table_name: Table containing the vector column
        column_name: Vector column name
        index_name: Name for the index
        lists: Number of lists for ivfflat (default 100)
        index_type: Index type (ivfflat or hnsw)
        operator_class: Operator class for distance metric

    Returns:
        True if index was created, False if it already exists
    """
    # Check if index already exists
    check_sql = text("""
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = :index_name
    """)
    result = await session.execute(check_sql, {"index_name": index_name})
    if result.scalar():
        logger.info(f"Vector index {index_name} already exists")
        return False

    # Create the index
    if index_type == "ivfflat":
        create_sql = text(f"""
            CREATE INDEX {index_name}
            ON {table_name} USING ivfflat ({column_name} {operator_class})
            WITH (lists = {lists})
        """)
    elif index_type == "hnsw":
        create_sql = text(f"""
            CREATE INDEX {index_name}
            ON {table_name} USING hnsw ({column_name} {operator_class})
        """)
    else:
        raise ValueError(f"Unsupported index type: {index_type}")

    logger.info(f"Creating vector index {index_name} on {table_name}.{column_name}")
    await session.execute(create_sql)
    await session.commit()

    logger.info(f"Vector index {index_name} created successfully")
    return True


async def drop_vector_index(
    session: AsyncSession,
    index_name: str = "ix_memory_records_embedding",
) -> bool:
    """Drop a vector index.

    Args:
        session: Database session
        index_name: Name of the index to drop

    Returns:
        True if index was dropped, False if it didn't exist
    """
    check_sql = text("""
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = :index_name
    """)
    result = await session.execute(check_sql, {"index_name": index_name})
    if not result.scalar():
        logger.info(f"Vector index {index_name} does not exist")
        return False

    drop_sql = text(f"DROP INDEX {index_name}")
    await session.execute(drop_sql)
    await session.commit()

    logger.info(f"Vector index {index_name} dropped")
    return True


async def optimize_vector_index(
    session: AsyncSession,
    index_name: str = "ix_memory_records_embedding",
    lists: int | None = None,
) -> bool:
    """Optimize/rebuild a vector index.

    Args:
        session: Database session
        index_name: Name of the index to optimize
        lists: New lists parameter (for ivfflat). If None, keeps current value.

    Returns:
        True if index was optimized
    """
    # For ivfflat, we need to REINDEX or recreate with new parameters
    # Get current index info
    info = await get_vector_index_info(session, index_name)
    if not info:
        logger.warning(f"Index {index_name} not found for optimization")
        return False

    if info.index_type == "ivfflat" and lists is not None:
        # Recreate with new lists parameter
        await drop_vector_index(session, index_name)
        await create_vector_index(
            session,
            table_name=info.table_name,
            column_name=info.column_name,
            index_name=index_name,
            lists=lists,
        )
        logger.info(f"Vector index {index_name} optimized with lists={lists}")
    else:
        # Just REINDEX
        reindex_sql = text(f"REINDEX INDEX {index_name}")
        await session.execute(reindex_sql)
        await session.commit()
        logger.info(f"Vector index {index_name} reindexed")

    return True


async def get_vector_index_info(
    session: AsyncSession,
    index_name: str,
) -> VectorIndexStats | None:
    """Get information about a vector index.

    Args:
        session: Database session
        index_name: Name of the index

    Returns:
        VectorIndexStats or None if not found
    """
    # Get index info from pg_indexes and pg_class
    sql = text("""
        SELECT
            i.indexname as index_name,
            i.tablename as table_name,
            a.attname as column_name,
            am.amname as index_type,
            pg_size_pretty(pg_relation_size(i.indexrelid)) as size_pretty,
            pg_relation_size(i.indexrelid) as size_bytes,
            c.reltuples as tuple_count,
            c.relpages as pages
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        JOIN pg_index idx ON idx.indexrelid = c.oid
        JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
        JOIN pg_am am ON am.oid = c.relam
        WHERE i.schemaname = 'public' AND i.indexname = :index_name
    """)

    result = await session.execute(sql, {"index_name": index_name})
    row = result.first()

    if not row:
        return None

    # Parse index options for ivfflat lists
    lists = None
    probes = None
    if row.index_type == "ivfflat":
        options_sql = text("""
            SELECT array_to_string(reloptions, ',') as options
            FROM pg_class
            WHERE relname = :index_name
        """)
        options_result = await session.execute(options_sql, {"index_name": index_name})
        options_row = options_result.first()
        if options_row and options_row.options:
            # Parse options like "lists=100"
            for opt in options_row.options.split(","):
                if "=" in opt:
                    key, val = opt.split("=")
                    if key.strip() == "lists":
                        lists = int(val.strip())
                    elif key.strip() == "probes":
                        probes = int(val.strip())

    return VectorIndexStats(
        index_name=row.index_name,
        table_name=row.table_name,
        column_name=row.column_name,
        index_type=row.index_type,
        lists=lists,
        probes=probes,
        size_bytes=row.size_bytes,
        size_pretty=row.size_pretty,
        tuple_count=int(row.tuple_count) if row.tuple_count else 0,
        pages=row.pages or 0,
    )


async def list_vector_indexes(session: AsyncSession) -> list[VectorIndexStats]:
    """List all vector indexes in the database.

    Args:
        session: Database session

    Returns:
        List of VectorIndexStats
    """
    sql = text("""
        SELECT
            i.indexname as index_name,
            i.tablename as table_name,
            a.attname as column_name,
            am.amname as index_type,
            pg_size_pretty(pg_relation_size(c.oid)) as size_pretty,
            pg_relation_size(c.oid) as size_bytes,
            c.reltuples as tuple_count,
            c.relpages as pages
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        JOIN pg_index idx ON idx.indexrelid = c.oid
        JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
        JOIN pg_am am ON am.oid = c.relam
        WHERE i.schemaname = 'public'
        AND am.amname IN ('ivfflat', 'hnsw')
    """)

    result = await session.execute(sql)
    rows = result.all()

    indexes = []
    for row in rows:
        # Get lists/probes for ivfflat
        lists = None
        probes = None
        if row.index_type == "ivfflat":
            options_sql = text("""
                SELECT array_to_string(reloptions, ',') as options
                FROM pg_class
                WHERE relname = :index_name
            """)
            options_result = await session.execute(options_sql, {"index_name": row.index_name})
            options_row = options_result.first()
            if options_row and options_row.options:
                for opt in options_row.options.split(","):
                    if "=" in opt:
                        key, val = opt.split("=")
                        if key.strip() == "lists":
                            lists = int(val.strip())
                        elif key.strip() == "probes":
                            probes = int(val.strip())

        indexes.append(
            VectorIndexStats(
                index_name=row.index_name,
                table_name=row.table_name,
                column_name=row.column_name,
                index_type=row.index_type,
                lists=lists,
                probes=probes,
                size_bytes=row.size_bytes,
                size_pretty=row.size_pretty,
                tuple_count=int(row.tuple_count) if row.tuple_count else 0,
                pages=row.pages or 0,
            )
        )

    return indexes


async def analyze_vector_index(
    session: AsyncSession,
    index_name: str = "ix_memory_records_embedding",
) -> dict:
    """Analyze vector index performance and health.

    Args:
        session: Database session
        index_name: Name of the index to analyze

    Returns:
        Dictionary with analysis results
    """
    info = await get_vector_index_info(session, index_name)
    if not info:
        return {"error": f"Index {index_name} not found"}

    # Get table stats for comparison
    table_sql = text(f"""
        SELECT
            pg_size_pretty(pg_total_relation_size('{info.table_name}')) as table_size,
            pg_total_relation_size('{info.table_name}') as table_size_bytes,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE relname = '{info.table_name}'
    """)
    table_result = await session.execute(table_sql)
    table_row = table_result.first()

    # Calculate index-to-table ratio
    index_ratio = 0.0
    if table_row and table_row.table_size_bytes > 0:
        index_ratio = info.size_bytes / table_row.table_size_bytes

    # Check if ANALYZE has been run recently
    analyze_sql = text(f"""
        SELECT last_analyze, last_autoanalyze
        FROM pg_stat_user_tables
        WHERE relname = '{info.table_name}'
    """)
    analyze_result = await session.execute(analyze_sql)
    analyze_row = analyze_result.first()

    return {
        "index": {
            "name": info.index_name,
            "type": info.index_type,
            "table": info.table_name,
            "column": info.column_name,
            "size": info.size_pretty,
            "size_bytes": info.size_bytes,
            "lists": info.lists,
            "probes": info.probes,
        },
        "table": {
            "size": table_row.table_size if table_row else "unknown",
            "size_bytes": table_row.table_size_bytes if table_row else 0,
            "row_count": table_row.row_count if table_row else 0,
        },
        "index_ratio": round(index_ratio, 4),
        "last_analyze": str(analyze_row.last_analyze) if analyze_row and analyze_row.last_analyze else "never",
        "last_autoanalyze": str(analyze_row.last_autoanalyze) if analyze_row and analyze_row.last_autoanalyze else "never",
        "recommendations": _generate_recommendations(info, table_row, index_ratio),
    }


def _generate_recommendations(
    info: VectorIndexStats,
    table_row: object | None,
    index_ratio: float,
) -> list[str]:
    """Generate optimization recommendations."""
    recommendations = []

    if info.index_type == "ivfflat":
        if info.lists is None:
            recommendations.append("Could not determine lists parameter; consider recreating index with explicit lists")
        elif info.lists < 100 and (table_row and table_row.row_count and table_row.row_count > 100000):
            recommendations.append(f"Lists ({info.lists}) may be too low for {table_row.row_count} rows; consider increasing to 100-1000")
        elif info.lists and info.lists > 1000 and (table_row and table_row.row_count and table_row.row_count < 10000):
            recommendations.append(f"Lists ({info.lists}) may be too high for {table_row.row_count} rows; consider reducing")

    if index_ratio > 0.5:
        recommendations.append("Index size is >50% of table size; consider HNSW index for better space efficiency")

    if table_row and table_row.row_count and table_row.row_count > 1000000 and info.index_type == "ivfflat":
        recommendations.append("Consider HNSW index for better query performance at scale")

    if not recommendations:
        recommendations.append("Index appears healthy")

    return recommendations


async def set_ivfflat_probes(
    session: AsyncSession,
    probes: int = 10,
) -> None:
    """Set the number of probes for ivfflat index searches.

    Args:
        session: Database session
        probes: Number of probes (higher = more accurate, slower)
    """
    sql = text(f"SET ivfflat.probes = {probes}")
    await session.execute(sql)
    logger.info(f"Set ivfflat.probes = {probes}")