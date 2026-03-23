# PR Summary: Replace Zep Cloud with Neo4j + LangChain

## Goal

Replace the cloud-hosted `zep-cloud` SDK (which required a Zep API key and an external service) with a fully local alternative — Neo4j graph database + LangChain — so the entire knowledge-graph pipeline runs on your own infrastructure with no third-party dependency.

---

## What Was Done

### Dependency Changes
- **Removed** `zep-cloud==3.13.0` from `pyproject.toml`, `requirements.txt`, and `uv.lock`
- **Added** `neo4j>=5.0.0` and `langchain-community>=0.2.0` (via `uv add`)

---

### Configuration
| Before | After |
|---|---|
| `Config.ZEP_API_KEY` | `Config.NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` |

- `.env.example` updated with Neo4j connection vars and a ready-to-paste `docker run` command
- `docker-compose.yml` gains a `neo4j` service with a persistent volume; the `mirofish` service depends on it

---

### New File: `app/utils/neo4j_graph.py`
- `GraphNode` / `GraphEdge` dataclasses, interface-compatible with the old Zep SDK objects so downstream code required minimal changes
- `get_driver()` — creates and returns the Neo4j driver
- `init_graph_schema()` — creates indexes and a `(graph_id, name)` uniqueness constraint to prevent race conditions
- `node_from_record()` / `edge_from_record()` — convert raw Cypher records to dataclasses

---

### Rewritten/Updated Services

| File | What Changed |
|---|---|
| `app/utils/zep_paging.py` | Zep cursor-based pagination → Neo4j `SKIP/LIMIT` Cypher queries; public API unchanged |
| `app/services/graph_builder.py` | Uses LLM to extract entities/relationships from each text chunk, stores them in Neo4j via `MERGE`/`CREATE`; processing is now synchronous |
| `app/services/zep_entity_reader.py` | Reads entities from Neo4j via Cypher instead of Zep; same public API |
| `app/services/zep_graph_memory_updater.py` | Agent activity batches stored as `ActivityNode` nodes in Neo4j |
| `app/services/zep_tools.py` | Graph search uses Cypher keyword matching; also searches `ActivityNode.description` |
| `app/services/oasis_profile_generator.py` | Entity context enrichment uses Cypher `CONTAINS` queries instead of Zep search API |

---

### Entity Extraction (Replaces Zep's Built-in NLP)

```python
# graph_builder.py — called per text chunk
def _extract_entities_from_chunk(self, text: str, ontology: dict) -> dict:
    return self.llm.chat_json(
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user",   "content": user_prompt}],
        temperature=0.0,
    )
    # Returns {"nodes": [...], "relationships": [...]}
    # Stored via MERGE (nodes) + CREATE (edges) in Neo4j
```

---

### API Layer
- `api/graph.py` and `api/simulation.py`: config guards updated from `ZEP_API_KEY` to `NEO4J_URI`
- `GraphBuilderService()` no longer accepts an `api_key` argument

---

## Summary

Everything that previously called the Zep Cloud API now talks to a local Neo4j instance instead. The public interfaces of all services were preserved, so no changes were required elsewhere in the application.
