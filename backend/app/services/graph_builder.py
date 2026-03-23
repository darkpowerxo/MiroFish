"""
图谱构建服务
接口2：使用Neo4j + LangChain构建知识图谱（替代Zep Cloud）
"""

import json
import os
import time
import uuid
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from neo4j import Driver

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.neo4j_graph import get_driver, init_graph_schema
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from .text_processor import TextProcessor

logger = get_logger('mirofish.graph_builder')


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    图谱构建服务
    负责调用LLM提取实体/关系并存储到Neo4j知识图谱
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        # 兼容旧调用方传入的 api_key 参数（忽略）
        api_key: Optional[str] = None,
    ):
        self.driver: Driver = get_driver()
        init_graph_schema(self.driver)
        self._llm_client: Optional[LLMClient] = None
        self.task_manager = TaskManager()

    @property
    def llm(self) -> LLMClient:
        """延迟初始化LLM客户端"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    # ------------------------------------------------------------------
    # 公开接口：异步构建
    # ------------------------------------------------------------------

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        """
        异步构建图谱

        Returns:
            任务ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
    ):
        """图谱构建工作线程"""
        try:
            self.task_manager.update_task(
                task_id, status=TaskStatus.PROCESSING, progress=5, message="开始构建图谱..."
            )

            # 1. 创建图谱（生成ID，初始化元数据）
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(task_id, progress=10, message=f"图谱已创建: {graph_id}")

            # 2. 保存本体信息
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(task_id, progress=15, message="本体已设置")

            # 3. 文本分块
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id, progress=20, message=f"文本已分割为 {total_chunks} 个块"
            )

            # 4. 分批提取实体并存入Neo4j
            episode_uuids = self.add_text_batches(
                graph_id,
                chunks,
                batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.7),  # 20-90%
                    message=msg,
                ),
            )

            # 5. 等待处理完成（Neo4j同步处理，立即完成）
            self.task_manager.update_task(task_id, progress=90, message="处理完成，获取图谱信息...")
            self._wait_for_episodes(episode_uuids)

            # 6. 获取图谱信息
            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(
                task_id,
                {
                    "graph_id": graph_id,
                    "graph_info": graph_info.to_dict(),
                    "chunks_processed": total_chunks,
                },
            )

        except Exception as e:
            import traceback

            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def create_graph(self, name: str) -> str:
        """创建图谱元数据节点，返回graph_id"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"

        with self.driver.session() as session:
            session.run(
                """
                MERGE (m:GraphMeta {graph_id: $graph_id})
                ON CREATE SET m.name = $name, m.created_at = $created_at
                """,
                graph_id=graph_id,
                name=name,
                created_at=datetime.now().isoformat(),
            )

        logger.info(f"图谱已创建: {graph_id} (name={name})")
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """将本体定义存储到图谱元数据中"""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (m:GraphMeta {graph_id: $graph_id})
                SET m.ontology_json = $ontology_json
                """,
                graph_id=graph_id,
                ontology_json=json.dumps(ontology, ensure_ascii=False),
            )
        logger.info(f"本体已存储到图谱: {graph_id}")

    def _get_ontology(self, graph_id: str) -> Dict[str, Any]:
        """从Neo4j读取图谱本体"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (m:GraphMeta {graph_id: $graph_id}) RETURN m.ontology_json AS ontology_json",
                graph_id=graph_id,
            )
            record = result.single()
            if record and record["ontology_json"]:
                try:
                    return json.loads(record["ontology_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return {}

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        """
        分批提取文本中的实体/关系并存入Neo4j。
        返回每个处理批次的ID列表（用于兼容 _wait_for_episodes 接口）。
        """
        ontology = self._get_ontology(graph_id)
        episode_ids: List[str] = []
        total_chunks = len(chunks)

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    f"处理第 {batch_num}/{total_batches} 批 ({len(batch_chunks)} 块)...",
                    progress,
                )

            for chunk in batch_chunks:
                ep_id = uuid.uuid4().hex
                try:
                    extracted = self._extract_entities_from_chunk(chunk, ontology)
                    self._store_extracted_entities(graph_id, extracted)
                    episode_ids.append(ep_id)
                except Exception as e:
                    logger.warning(f"批次 {batch_num} 处理失败: {str(e)}")
                    episode_ids.append(ep_id)

            # 避免LLM API请求过快
            if i + batch_size < total_chunks:
                time.sleep(0.5)

        return episode_ids

    def _extract_entities_from_chunk(self, text: str, ontology: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用LLM从文本块中提取实体和关系。
        """
        entity_types = [e["name"] for e in ontology.get("entity_types", [])]
        edge_types = [e["name"] for e in ontology.get("edge_types", [])]

        system_prompt = (
            "You are a knowledge graph extraction expert. "
            "Extract entities and relationships from the given text according to the provided ontology. "
            "Return valid JSON only."
        )

        allowed_entities = ", ".join(entity_types) if entity_types else "any relevant entities"
        allowed_relations = ", ".join(edge_types) if edge_types else "any relevant relationships"

        # Truncate text to 3000 chars to stay within typical LLM context/cost limits
        # while still capturing enough context for entity extraction.
        user_prompt = f"""Extract entities and relationships from the text below.

Allowed entity types: {allowed_entities}
Allowed relationship types: {allowed_relations}

Text:
{text[:3000]}

Return a JSON object with this exact structure:
{{
  "nodes": [
    {{
      "name": "entity name",
      "type": "entity type",
      "summary": "brief description",
      "attributes": {{}}
    }}
  ],
  "relationships": [
    {{
      "source": "source entity name",
      "target": "target entity name",
      "type": "relationship type",
      "fact": "human-readable description"
    }}
  ]
}}

Only extract what is explicitly stated in the text."""

        try:
            return self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
        except Exception as e:
            logger.warning(f"实体提取失败: {str(e)[:100]}")
            return {"nodes": [], "relationships": []}

    def _store_extracted_entities(self, graph_id: str, extracted: Dict[str, Any]) -> None:
        """将LLM提取的实体和关系存入Neo4j"""
        nodes = extracted.get("nodes", [])
        relationships = extracted.get("relationships", [])

        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(relationships, list):
            relationships = []

        # 存储节点（MERGE by name，同名实体自动合并）
        node_name_to_uuid: Dict[str, str] = {}
        with self.driver.session() as session:
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                name = str(node.get("name", "")).strip()
                if not name:
                    continue

                node_uuid = uuid.uuid4().hex
                entity_type = str(node.get("type", "Entity")).strip() or "Entity"
                node_labels = ["Entity"]
                if entity_type and entity_type not in node_labels:
                    node_labels.append(entity_type)

                summary = str(node.get("summary", ""))
                attrs_json = json.dumps(node.get("attributes", {}), ensure_ascii=False)

                result = session.run(
                    """
                    MERGE (n:GraphNode {graph_id: $graph_id, name: $name})
                    ON CREATE SET
                        n.uuid        = $uuid,
                        n.node_labels = $node_labels,
                        n.summary     = $summary,
                        n.attributes_json = $attrs_json,
                        n.created_at  = $created_at
                    ON MATCH SET
                        n.summary = CASE WHEN n.summary = '' THEN $summary ELSE n.summary END
                    RETURN n.uuid AS uuid
                    """,
                    graph_id=graph_id,
                    name=name,
                    uuid=node_uuid,
                    node_labels=node_labels,
                    summary=summary,
                    attrs_json=attrs_json,
                    created_at=datetime.now().isoformat(),
                )
                record = result.single()
                node_name_to_uuid[name] = record["uuid"] if record else node_uuid

            # 存储关系
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue
                source_name = str(rel.get("source", "")).strip()
                target_name = str(rel.get("target", "")).strip()
                rel_type = str(rel.get("type", "RELATED_TO")).strip() or "RELATED_TO"
                fact = str(rel.get("fact", "")).strip()

                if not source_name or not target_name:
                    continue

                edge_uuid = uuid.uuid4().hex
                # 确保source/target节点存在（如果LLM只生成了关系但没有节点）
                for nname in (source_name, target_name):
                    if nname not in node_name_to_uuid:
                        r2 = session.run(
                            """
                            MERGE (n:GraphNode {graph_id: $graph_id, name: $name})
                            ON CREATE SET
                                n.uuid = $uuid,
                                n.node_labels = ['Entity'],
                                n.summary = '',
                                n.attributes_json = '{}',
                                n.created_at = $created_at
                            RETURN n.uuid AS uuid
                            """,
                            graph_id=graph_id,
                            name=nname,
                            uuid=uuid.uuid4().hex,
                            created_at=datetime.now().isoformat(),
                        )
                        rec = r2.single()
                        if rec:
                            node_name_to_uuid[nname] = rec["uuid"]

                source_uuid = node_name_to_uuid.get(source_name, "")
                target_uuid = node_name_to_uuid.get(target_name, "")
                if not source_uuid or not target_uuid:
                    continue

                session.run(
                    """
                    MATCH (s:GraphNode {graph_id: $graph_id, uuid: $source_uuid})
                    MATCH (t:GraphNode {graph_id: $graph_id, uuid: $target_uuid})
                    CREATE (s)-[r:GRAPH_EDGE {
                        uuid: $edge_uuid,
                        graph_id: $graph_id,
                        name: $rel_type,
                        fact: $fact,
                        source_node_uuid: $source_uuid,
                        target_node_uuid: $target_uuid,
                        created_at: $created_at
                    }]->(t)
                    """,
                    graph_id=graph_id,
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    edge_uuid=edge_uuid,
                    rel_type=rel_type,
                    fact=fact,
                    created_at=datetime.now().isoformat(),
                )

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600,
    ):
        """
        Neo4j同步处理，无需等待。
        保留此方法以兼容调用方（graph.py API层）的调用签名。
        """
        if progress_callback:
            progress_callback(f"处理完成: {len(episode_uuids)}/{len(episode_uuids)}", 1.0)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱统计信息"""
        nodes = fetch_all_nodes(self.driver, graph_id)
        edges = fetch_all_edges(self.driver, graph_id)

        entity_types: set = set()
        for node in nodes:
            for label in node.labels:
                if label not in ("Entity", "Node"):
                    entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types),
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        获取完整图谱数据（包含详细信息）

        Returns:
            包含nodes和edges的字典
        """
        nodes = fetch_all_nodes(self.driver, graph_id)
        edges = fetch_all_edges(self.driver, graph_id)

        node_map = {node.uuid_: node.name for node in nodes}

        nodes_data = [
            {
                "uuid": node.uuid_,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": node.created_at,
            }
            for node in nodes
        ]

        edges_data = [
            {
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": edge.name or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": edge.created_at,
                "valid_at": edge.valid_at,
                "invalid_at": edge.invalid_at,
                "expired_at": edge.expired_at,
                "episodes": [],
            }
            for edge in edges
        ]

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        """删除图谱（节点、边及元数据）"""
        with self.driver.session() as session:
            # 删除图谱边
            session.run(
                "MATCH ()-[r:GRAPH_EDGE {graph_id: $graph_id}]->() DELETE r",
                graph_id=graph_id,
            )
            # 删除图谱节点
            session.run(
                "MATCH (n:GraphNode {graph_id: $graph_id}) DELETE n",
                graph_id=graph_id,
            )
            # 删除元数据
            session.run(
                "MATCH (m:GraphMeta {graph_id: $graph_id}) DELETE m",
                graph_id=graph_id,
            )
        logger.info(f"图谱已删除: {graph_id}")

