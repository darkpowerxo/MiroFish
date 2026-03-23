"""Neo4j Graph 分页读取工具。

替代原 Zep 分页工具，通过 Cypher 查询从 Neo4j 中分页获取图谱节点和边。
对调用方透明地返回完整列表，数据结构保持与原 Zep 接口兼容。
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
    """分页获取图谱节点，最多返回 max_items 条（默认 2000）。"""
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
    """分页获取图谱所有边，返回完整列表。"""
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
