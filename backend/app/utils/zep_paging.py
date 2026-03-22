"""Neo4j Graph paging read utility.

Replaces the original Zep paging tool, fetching graph nodes and edges from Neo4j in pages via Cypher queries.
Returns a complete list transparently to the caller; data structure remains compatible with the original Zep interface.
"""

from __future__ import annotations

from typing import Any

from neo4j import Driver

from .logger import get_logger
from .neo4j_graph import GraphEdge, GraphNode, edge_from_record, node_from_record

logger = get_logger('mirofish.neo4j_paging')

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000


def fetch_all_nodes(
    driver: Driver,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    **_kwargs: Any,
) -> list[GraphNode]:
    """Fetch graph nodes with pagination, returning at most max_items entries (default 2000)."""
    all_nodes: list[GraphNode] = []
    skip = 0

    while True:
        with driver.session() as session:
            result = session.run(
                "MATCH (n:GraphNode {graph_id: $graph_id}) "
                "RETURN n ORDER BY n.uuid "
                "SKIP $skip LIMIT $limit",
                graph_id=graph_id,
                skip=skip,
                limit=page_size,
            )
            batch = [node_from_record(record["n"]) for record in result]

        if not batch:
            break

        all_nodes.extend(batch)
        if len(all_nodes) >= max_items:
            all_nodes = all_nodes[:max_items]
            logger.warning(
                f"Node count reached limit ({max_items}), stopping pagination for graph {graph_id}"
            )
            break
        if len(batch) < page_size:
            break

        skip += len(batch)

    return all_nodes


def fetch_all_edges(
    driver: Driver,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    **_kwargs: Any,
) -> list[GraphEdge]:
    """Fetch all graph edges with pagination, returning the complete list."""
    all_edges: list[GraphEdge] = []
    skip = 0

    while True:
        with driver.session() as session:
            result = session.run(
                "MATCH ()-[r:GRAPH_EDGE {graph_id: $graph_id}]->() "
                "RETURN r ORDER BY r.uuid "
                "SKIP $skip LIMIT $limit",
                graph_id=graph_id,
                skip=skip,
                limit=page_size,
            )
            batch = [edge_from_record(record["r"]) for record in result]

        if not batch:
            break

        all_edges.extend(batch)
        if len(batch) < page_size:
            break

        skip += len(batch)

    return all_edges
