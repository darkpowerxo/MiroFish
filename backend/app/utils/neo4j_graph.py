"""
Neo4j graph database client utility
Provides Zep-compatible node/edge data structures and Neo4j connection management
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
    Node data structure, compatible with the original Zep node interface.
    The uuid_ attribute name is kept consistent with the zep-cloud SDK, enabling seamless switching for other modules.
    """
    uuid_: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    created_at: Optional[str] = None
    # Synchronous processing: node is considered processed upon creation
    processed: bool = True


@dataclass
class GraphEdge:
    """
    Edge data structure, compatible with the original Zep edge interface.
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
    Create and return a Neo4j driver instance based on Config.
    The caller is responsible for closing the driver after use (driver.close()).
    """
    return GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
    )


def init_graph_schema(driver: Driver) -> None:
    """
    Initialize Neo4j indexes and constraints to improve query performance.
    Idempotent operation, can be called repeatedly.
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
    """Convert a Neo4j node record to a GraphNode dataclass"""
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
    """Convert a Neo4j relationship record to a GraphEdge dataclass"""
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
