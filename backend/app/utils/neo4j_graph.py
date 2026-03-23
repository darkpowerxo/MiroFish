"""
Neo4j图数据库客户端工具
提供与Zep兼容的节点/边数据结构和Neo4j连接管理
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver
from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.neo4j_graph')


@dataclass
class GraphNode:
    """
    节点数据结构，与原Zep节点接口兼容。
    uuid_ 属性名保持与 zep-cloud SDK 一致，便于其他模块无缝切换。
    """
    uuid_: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    created_at: Optional[str] = None
    # 同步处理：节点创建时即视为已处理完成
    processed: bool = True


@dataclass
class GraphEdge:
    """
    边数据结构，与原Zep边接口兼容。
    """
    uuid_: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None


def get_driver() -> Driver:
    """
    根据Config创建并返回Neo4j驱动实例。
    调用方负责在用完后关闭驱动（driver.close()）。
    """
    return GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
    )


def init_graph_schema(driver: Driver) -> None:
    """
    初始化Neo4j索引和约束，提升查询性能。
    幂等操作，可重复调用。
    """
    with driver.session() as session:
        # Uniqueness constraint prevents duplicate nodes and eliminates MERGE race conditions
        session.run(
            "CREATE CONSTRAINT graphnode_unique IF NOT EXISTS "
            "FOR (n:GraphNode) REQUIRE (n.graph_id, n.name) IS UNIQUE"
        )
        session.run(
            "CREATE INDEX graphnode_graph_uuid IF NOT EXISTS "
            "FOR (n:GraphNode) ON (n.graph_id, n.uuid)"
        )
        session.run(
            "CREATE INDEX graphedge_graph_uuid IF NOT EXISTS "
            "FOR ()-[r:GRAPH_EDGE]-() ON (r.graph_id, r.uuid)"
        )
    logger.debug("Neo4j schema initialized")


def node_from_record(record_node: Any) -> GraphNode:
    """将Neo4j节点记录转换为GraphNode数据类"""
    props = dict(record_node)
    raw_attrs = props.get("attributes_json", "{}")
    try:
        attributes = json.loads(raw_attrs) if isinstance(raw_attrs, str) else raw_attrs or {}
    except (json.JSONDecodeError, TypeError):
        attributes = {}

    return GraphNode(
        uuid_=props.get("uuid", ""),
        name=props.get("name", ""),
        labels=props.get("node_labels", ["Entity"]),
        summary=props.get("summary", ""),
        attributes=attributes,
        created_at=props.get("created_at"),
    )


def edge_from_record(record_edge: Any) -> GraphEdge:
    """将Neo4j关系记录转换为GraphEdge数据类"""
    props = dict(record_edge)
    return GraphEdge(
        uuid_=props.get("uuid", ""),
        name=props.get("name", ""),
        fact=props.get("fact", ""),
        source_node_uuid=props.get("source_node_uuid", ""),
        target_node_uuid=props.get("target_node_uuid", ""),
        created_at=props.get("created_at"),
        valid_at=props.get("valid_at"),
        invalid_at=props.get("invalid_at"),
        expired_at=props.get("expired_at"),
    )
