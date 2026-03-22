"""
Entity reading and filtering service
Reads nodes from the Neo4j graph and filters those matching predefined entity types
(Replaces the original Zep entity reader)
"""

import time
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
from dataclasses import dataclass, field

from neo4j import Driver

from ..config import Config
from ..utils.logger import get_logger
from ..utils.neo4j_graph import get_driver
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_entity_reader')

T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """Get entity types (excluding default Entity and Node labels)"""
        for label in self.labels:
            if label not in ("Entity", "Node"):
                return label
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Entity reading and filtering service (Neo4j implementation)

    Main functions:
    1. Read all nodes from the Neo4j graph
    2. Filter nodes matching predefined entity types
    3. Retrieve related edges and linked-node info for each entity
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key kept for backward compatibility; Neo4j config is used internally
        self.driver: Driver = get_driver()

    def _call_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0,
    ) -> T:
        """Call an operation with retry logic"""
        last_exception = None
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"{operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"{operation_name} failed after {max_retries} attempts: {str(e)}")

        raise last_exception

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all nodes in the graph"""
        logger.info(f"Fetching all nodes for graph {graph_id}...")
        nodes = fetch_all_nodes(self.driver, graph_id)

        nodes_data = [
            {
                "uuid": node.uuid_,
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            }
            for node in nodes
        ]

        logger.info(f"Fetched {len(nodes_data)} nodes")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all edges in the graph"""
        logger.info(f"Fetching all edges for graph {graph_id}...")
        edges = fetch_all_edges(self.driver, graph_id)

        edges_data = [
            {
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            }
            for edge in edges
        ]

        logger.info(f"Fetched {len(edges_data)} edges")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """Get all edges related to a specific node"""
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n:GraphNode {uuid: $uuid})-[r:GRAPH_EDGE]-(m:GraphNode)
                    RETURN r, n.uuid AS n_uuid, m.uuid AS m_uuid
                    """,
                    uuid=node_uuid,
                )
                edges_data = []
                for record in result:
                    edge = record["r"]
                    props = dict(edge)
                    edges_data.append({
                        "uuid": props.get("uuid", ""),
                        "name": props.get("name", ""),
                        "fact": props.get("fact", ""),
                        "source_node_uuid": props.get("source_node_uuid", ""),
                        "target_node_uuid": props.get("target_node_uuid", ""),
                        "attributes": {},
                    })
            return edges_data
        except Exception as e:
            logger.warning(f"Failed to get edges for node {node_uuid}: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        """
        Filter nodes matching predefined entity types

        Filter logic:
        - Keep nodes whose labels include at least one label other than "Entity" or "Node"
        """
        logger.info(f"Starting entity filtering for graph {graph_id}...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = [l for l in labels if l not in ("Entity", "Node")]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids: Set[str] = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        rn = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": rn["uuid"],
                            "name": rn["name"],
                            "labels": rn["labels"],
                            "summary": rn.get("summary", ""),
                        })
                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(
            f"Filtering complete: total nodes {total_count}, matched {len(filtered_entities)}, "
            f"entity types: {entity_types_found}"
        )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str,
    ) -> Optional[EntityNode]:
        """Get a single entity with its full context (edges and linked nodes)"""
        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (n:GraphNode {uuid: $uuid, graph_id: $graph_id}) RETURN n",
                    uuid=entity_uuid,
                    graph_id=graph_id,
                )
                record = result.single()
                if not record:
                    return None

            import json
            node = dict(record["n"])
            raw_attrs = node.get("attributes_json", "{}")
            try:
                attributes = json.loads(raw_attrs) if isinstance(raw_attrs, str) else raw_attrs or {}
            except (json.JSONDecodeError, TypeError):
                attributes = {}

            # Get node edges
            edges = self.get_node_edges(entity_uuid)

            # Get all nodes for association lookup
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids: Set[str] = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    rn = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": rn["uuid"],
                        "name": rn["name"],
                        "labels": rn["labels"],
                        "summary": rn.get("summary", ""),
                    })

            return EntityNode(
                uuid=node.get("uuid", entity_uuid),
                name=node.get("name", ""),
                labels=node.get("node_labels", ["Entity"]),
                summary=node.get("summary", ""),
                attributes=attributes,
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"Failed to get entity {entity_uuid}: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        """Get all entities of a specified type"""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return result.entities

