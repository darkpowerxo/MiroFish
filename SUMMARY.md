# MiroFish — Project Summary

## What Is MiroFish?

MiroFish is a **next-generation AI prediction engine** built on multi-agent technology and swarm intelligence. It creates high-fidelity parallel digital worlds populated with intelligent agents to simulate and predict real-world outcomes.

**Core idea**: Feed it a document (news article, report, PDF), and it will:

1. Extract seed information and build a knowledge graph
2. Spawn thousands of AI agents with unique personalities and long-term memory
3. Run parallel social simulations (Twitter-like + Reddit-like platforms)
4. Analyze the results and generate actionable predictions

**Use cases**: Financial market prediction, political opinion simulation, public relations strategy testing, policy rehearsal, and creative storytelling.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11-3.12, Flask 3.0+ |
| Frontend | Vue 3, Vite, D3.js, Axios |
| Graph DB | Neo4j 6.1+ |
| Multi-Agent Sim | OASIS (CAMEL-AI) 0.2.5 |
| LLM | OpenAI-compatible API (Qwen-plus recommended) |
| Agent Memory | Zep Cloud |
| Packaging | uv (Python), npm (Node.js) |

---

## Prerequisites

| Tool | Version | Check |
| --- | --- | --- |
| Python | 3.11-3.12 | `python --version` |
| Node.js | 18+ | `node -v` |
| uv | Latest | `uv --version` |
| Neo4j | Any | - |
| Docker | Latest (optional) | `docker -v` |

Install `uv` if you do not have it:

```bash
pip install uv
```

---

## Setup

### 1. Clone and configure environment

```bash
git clone https://github.com/darkpowerxo/MiroFish.git
cd MiroFish

# Copy the example env file and fill in your keys
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# LLM - any OpenAI-compatible provider
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud (free tier works) - https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword

# Flask
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
SECRET_KEY=mirofish-secret-key

# Simulation defaults
OASIS_DEFAULT_MAX_ROUNDS=10
REPORT_AGENT_MAX_TOOL_CALLS=5
REPORT_AGENT_MAX_REFLECTION_ROUNDS=2
REPORT_AGENT_TEMPERATURE=0.5
```

### 2. Install dependencies

```bash
# Install everything in one command
npm run setup:all
```

Or step by step:

```bash
npm run setup          # Frontend + root packages
npm run setup:backend  # Backend (creates Python virtual env automatically)
```

---

## Starting the Application

### Development mode (recommended)

```bash
npm run dev
```

This starts both frontend and backend concurrently.

| Service | URL |
| --- | --- |
| Frontend UI | <http://localhost:3000> |
| Backend API | <http://localhost:5001> |
| Health check | <http://localhost:5001/health> |

### Start individually

```bash
npm run backend    # Backend only
npm run frontend   # Frontend only
```

### Docker (alternative)

Make sure `.env` is configured, then:

```bash
docker compose up -d
```

| Service | URL |
| --- | --- |
| Frontend | <http://localhost:3000> |
| Backend | <http://localhost:5001> |
| Neo4j Browser | <http://localhost:7474> |

---

## How to Use It - 5-Step Workflow

Open <http://localhost:3000> in your browser. The UI guides you through five sequential steps:

### Step 1 - Graph Building

- On the home page, upload one or more documents (PDF, MD, or TXT, max 50 MB each)
- Enter a simulation goal/question in the text field
- Click **Build Graph** - the LLM extracts entities and relationships and writes them to Neo4j
- Watch the knowledge graph appear in real time on the left panel

### Step 2 - Environment Setup

- After the graph is ready, click **Initialize Simulation**
- The system reads graph entities and generates agent personas via the LLM
- Each agent gets a unique personality, role, and Zep memory session
- Adjust simulation parameters if needed (platforms, number of agents)

### Step 3 - Run Simulation

- Click **Start Simulation**
- Agents interact across two parallel platforms:
  - **Twitter/Info Plaza**: posts, likes, reposts, quotes, follows
  - **Reddit**: posts, comments, upvotes/downvotes, search, trending
- Watch live progress bars for each platform
- Simulation runs for the configured number of rounds (default: 10)

### Step 4 - Report Generation

- Once simulation finishes, click **Generate Report**
- The ReportAgent analyzes all agent interactions, post histories, and graph state
- A structured prediction report with insights is produced
- Download the report or view it inline

### Step 5 - Deep Interaction

- Chat directly with any agent from the simulation
- Ask the ReportAgent follow-up questions
- Interview agents about their decisions and behaviors during the simulation

---

## Project Structure

```text
MiroFish/
+-- .env.example              # Environment variable template
+-- docker-compose.yml        # Docker services (neo4j, app)
+-- Dockerfile                # Container build file
+-- package.json              # Root npm scripts (dev, setup, build)
+-- backend/
|   +-- run.py                # Flask entry point
|   +-- pyproject.toml        # uv project config
|   +-- requirements.txt      # Python dependencies
|   +-- app/
|       +-- config.py         # All env-driven configuration
|       +-- api/              # REST API blueprints
|       |   +-- graph.py      # /api/graph endpoints
|       |   +-- simulation.py # /api/simulation endpoints
|       |   +-- report.py     # /api/report endpoints
|       +-- models/           # Project and Task state models
|       +-- services/         # Core business logic
|       |   +-- ontology_generator.py      # LLM ontology extraction
|       |   +-- oasis_profile_generator.py # Agent persona creation
|       |   +-- simulation_runner.py       # OASIS simulation execution
|       |   +-- report_agent.py            # Report generation agent
|       |   +-- zep_*.py                   # Zep memory integration
|       +-- utils/
|           +-- neo4j_graph.py  # Neo4j driver wrapper
|           +-- llm_client.py   # LLM API client
|           +-- file_parser.py  # PDF/MD/TXT parsing
+-- frontend/
    +-- vite.config.js
    +-- src/
        +-- router/index.js   # Page routes
        +-- api/              # Axios API clients
        +-- views/            # Full-page components
        |   +-- Home.vue
        |   +-- MainView.vue
        |   +-- SimulationView.vue
        |   +-- SimulationRunView.vue
        |   +-- ReportView.vue
        |   +-- InteractionView.vue
        +-- components/       # Step components + GraphPanel
```

---

## Key API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Backend health check |
| `POST` | `/api/graph/ontology/generate` | Upload files, generate ontology |
| `GET` | `/api/graph/project/<id>` | Get project details |
| `GET` | `/api/graph/project/list` | List all projects |
| `POST` | `/api/simulation/create` | Initialize a simulation |
| `POST` | `/api/simulation/run` | Execute simulation |
| `GET` | `/api/simulation/<id>/run-status` | Poll simulation progress |
| `POST` | `/api/simulation/<id>/stop` | Stop a running simulation |
| `POST` | `/api/report/generate` | Trigger report generation |
| `GET` | `/api/report/<id>` | Retrieve report |
| `GET` | `/api/report/<id>/download` | Download report file |
| `POST` | `/api/report/<id>/chat` | Chat with ReportAgent |

---

## Tips

- **LLM cost warning**: Simulations consume significant LLM tokens. Start with fewer than 40 rounds while testing.
- **Zep Cloud**: The free monthly quota is sufficient for basic usage. Sign up at <https://app.getzep.com/>.
- **LLM compatibility**: Any OpenAI-compatible provider works. Alibaba Qwen-plus via Bailian is recommended for cost efficiency.
- **File uploads**: PDF, Markdown, and plain text are supported. Max 50 MB per file.
- **Neo4j**: Required to be running before starting the backend. Use the Docker Compose setup to get Neo4j automatically.
