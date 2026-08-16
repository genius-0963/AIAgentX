<p align="center">
  <img src=".github/assets/banner.jpg" alt="AIAgentX Banner" width="100%" />
</p>

<p align="center">
  <strong>Production-grade AI Agent Orchestration Platform</strong><br/>
  Multi-provider LLM support · Intelligent tool routing · Enterprise-grade reliability
</p>

<p align="center">
  <a href="https://github.com/AIAgentX/aiagentx/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/AIAgentX/aiagentx/ci.yml?branch=main&style=flat-square&logo=github&label=CI" alt="CI Status"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-≥3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"></a>
  <a href="https://redis.io/"><img src="https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis"></a>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API Reference</a> •
  <a href="#-deployment">Deployment</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🧠 What is AIAgentX?

**AIAgentX** is an open-source, production-ready platform for building, deploying, and orchestrating AI agents at scale. It provides a robust runtime with **multi-tenant isolation**, **versioned agent lifecycles**, **granular tool security**, and **real-time execution streaming** — all backed by a clean, domain-driven architecture.

Whether you're building a single conversational assistant or orchestrating a fleet of specialized agents, AIAgentX gives you the enterprise primitives you need without sacrificing developer experience.

```
┌─────────────────────────────────────────────────────────────────┐
│                         AIAgentX                                │
│                                                                 │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│   │  OpenAI  │   │Anthropic │   │  Google  │   │  Custom  │   │
│   │  GPT-4o  │   │  Claude  │   │  Gemini  │   │ Provider │   │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   │
│        └───────────────┴───────────────┴──────────────┘         │
│                         │                                       │
│              ┌──────────▼──────────┐                            │
│              │  Agent Orchestrator │                            │
│              │  ┌───────────────┐  │                            │
│              │  │  Tool Router  │  │                            │
│              │  └───────────────┘  │                            │
│              └──────────┬──────────┘                            │
│        ┌────────────────┼────────────────┐                     │
│   ┌────▼────┐    ┌──────▼──────┐   ┌─────▼─────┐              │
│   │  Web    │    │    Code     │   │   Data    │              │
│   │ Search  │    │  Executor   │   │ Analysis  │              │
│   └─────────┘    └─────────────┘   └───────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔌 Multi-Provider LLM Support
Seamlessly switch between **OpenAI**, **Anthropic**, and **Google** models through a unified provider abstraction. Built-in fallback routing and circuit breakers ensure reliability.

</td>
<td width="50%">

### 🏗️ Agent Versioning & Lifecycle
Manage agents as versioned aggregates: `draft` → `published` → `archived`. Published versions are **immutable**, ensuring deterministic, reproducible execution.

</td>
</tr>
<tr>
<td>

### 🔐 Enterprise Security
Row-Level Security (RLS) for full **multi-tenant data isolation**, JWT/API key authentication with granular scopes, and deny-by-default tool capability grants with human-in-the-loop approval.

</td>
<td>

### 🧰 Extensible Tool System
Register tools with JSON schemas and safety ratings. Agents only access **explicitly granted** tools, with input validation, egress filtering, and approval workflows for irreversible actions.

</td>
</tr>
<tr>
<td>

### 📡 Real-time Streaming
Server-Sent Events (SSE) stream execution in real-time with `Last-Event-ID` reconnection recovery. Watch your agents think, tool-call, and respond step by step.

</td>
<td>

### 💰 Cost & Budget Controls
Built-in budget guards with micro-unit money tracking, token usage accounting, `max_steps` limits, and run timeouts. Never exceed your LLM spend unexpectedly.

</td>
</tr>
<tr>
<td>

### 🧠 Tiered Memory System
Three memory modes: **Ephemeral** (per-run), **Session** (Redis + DB summary), and **Durable** (encrypted PostgreSQL + `pgvector` embeddings) for long-term agent knowledge.

</td>
<td>

### 📊 Observability & Resilience
Structured JSON logging via `structlog`, request tracing (`X-Request-ID`), OpenTelemetry hooks, retry with jittered backoff, and circuit breaking for all external calls.

</td>
</tr>
</table>

---

## 🏛️ Architecture

AIAgentX follows **Clean Architecture** and **Domain-Driven Design (DDD)** principles with strict dependency inversion:

```
  API Layer        Application Layer        Domain Layer        Infrastructure Layer
 ┌──────────┐     ┌──────────────────┐     ┌──────────────┐    ┌─────────────────────┐
 │ FastAPI   │────▶│   Use Cases      │────▶│  Entities    │◀───│  PostgreSQL + RLS   │
 │ Routers   │     │  (Agent, Run)    │     │  Value Objs  │    │  Redis Cache        │
 │ Middleware│     │                  │     │  Events      │    │  LLM Providers      │
 │ SSE Stream│     │                  │     │  Repo Ports  │    │  Auth (JWT/APIKey)  │
 └──────────┘     └──────────────────┘     └──────────────┘    │  Observability      │
                                                                └─────────────────────┘
```

### Project Structure

```
app/
├── api/                          # Interface Adapters — HTTP layer
│   ├── middleware/                # RequestID, Access logging, Error handling
│   └── v1/                       # Versioned REST endpoints
│       ├── health.py             # /healthz and /readyz probes
│       └── agents/               # Agent CRUD, versioning, tool grants
├── application/                  # Use Cases & Orchestration
│   └── use_cases/                # AgentUseCases, RunUseCases
├── domain/                       # Enterprise Business Rules (zero deps)
│   ├── entities/                 # Agent, Run, ToolGrant, Tenant, User
│   ├── events/                   # Domain events (AgentCreated, RunStateChanged)
│   ├── repositories/             # Repository port interfaces (Protocols)
│   └── value_objects/            # RunState, Money, TokenUsage
├── infrastructure/               # Frameworks & Drivers
│   ├── auth/                     # JWT decoding, API key verification
│   ├── cache/                    # Redis client & health checks
│   ├── db/                       # SQLAlchemy engine, models, repositories
│   │   └── migrations/           # Alembic migration versions
│   ├── observability/            # Structlog config, telemetry outbox
│   └── providers/                # LLM provider adapters (OpenAI, Anthropic)
└── workers/                      # Background execution engine & lease sweeper
```

### Agent Execution Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Orchestrator
    participant Provider as LLM Provider
    participant Tools as Tool Router
    participant DB as PostgreSQL

    Client->>API: POST /v1/agents/{id}/runs
    API->>DB: Create Run (queued)
    API-->>Client: 202 Accepted

    Note over Orchestrator: Worker claims lease

    loop Until complete or budget exceeded
        Orchestrator->>Provider: Send context + history
        Provider-->>Orchestrator: Response / Tool call
        alt Tool call requested
            Orchestrator->>Tools: Authorize & execute
            Tools-->>Orchestrator: Tool result
            Orchestrator->>DB: Save RunStep
        else Final response
            Orchestrator->>DB: Update Run → succeeded
        end
    end

    Client->>API: GET /v1/runs/{id}/events (SSE)
    API-->>Client: Stream steps in real-time
```

---

## 🚀 Quick Start

### Prerequisites

| Tool       | Version   | Purpose                  |
|------------|-----------|--------------------------|
| Python     | ≥ 3.12    | Runtime                  |
| Docker     | ≥ 24.0    | Services (Postgres, Redis) |
| uv         | ≥ 0.4     | Fast Python package manager |

### 1. Clone & Setup

```bash
# Clone the repository
git clone https://github.com/AIAgentX/aiagentx.git
cd aiagentx

# Run the automated setup
./scripts/dev.sh setup
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Required — at least one LLM provider
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Infrastructure (defaults work with docker-compose)
DATABASE_URL=postgresql+asyncpg://aiagentx:aiagentx@localhost:5432/aiagentx
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secure-random-secret-key
```

### 3. Start Services & Run

```bash
# Start PostgreSQL & Redis
docker compose up -d

# Run database migrations
./scripts/dev.sh migrate

# Launch the development server
./scripts/dev.sh start
```

The API is now live at **http://localhost:8000** 🎉

- 📖 **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📕 **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- 💚 **Health Check**: [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 4. Create Your First Agent

```bash
curl -X POST http://localhost:8000/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{
    "name": "research-assistant",
    "description": "An AI research assistant with web search capabilities",
    "system_prompt": "You are a helpful research assistant. Use web search to find accurate, up-to-date information.",
    "model_policy": {
      "provider": "openai",
      "model": "gpt-4o",
      "temperature": 0.7,
      "max_tokens": 4096
    },
    "memory_mode": "session"
  }'
```

---

## 📡 API Reference

### Health & Operations

| Method | Endpoint      | Description                                       |
|--------|---------------|---------------------------------------------------|
| `GET`  | `/healthz`    | Liveness probe (no external calls)                |
| `GET`  | `/readyz`     | Readiness probe (DB + Redis + migrations check)   |
| `GET`  | `/docs`       | Interactive OpenAPI documentation                 |

### Agent Management

| Method   | Endpoint                                          | Description                     |
|----------|---------------------------------------------------|---------------------------------|
| `POST`   | `/v1/agents`                                      | Create a new agent              |
| `GET`    | `/v1/agents`                                      | List all agents                 |
| `GET`    | `/v1/agents/{id}`                                 | Get agent details               |
| `PATCH`  | `/v1/agents/{id}`                                 | Update agent metadata           |
| `DELETE` | `/v1/agents/{id}`                                 | Soft-delete an agent            |
| `POST`   | `/v1/agents/{id}/versions`                        | Create new version (draft)      |
| `GET`    | `/v1/agents/{id}/versions`                        | List agent versions             |
| `POST`   | `/v1/agents/{id}/versions/{v}/publish`            | Publish version (immutable)     |
| `POST`   | `/v1/agents/{id}/versions/{v}/tool-grants`        | Grant tool to version           |

### Execution & Runs

| Method | Endpoint                      | Description                              |
|--------|-------------------------------|------------------------------------------|
| `POST` | `/v1/agents/{id}/runs`        | Submit a run (`Idempotency-Key` required)|
| `GET`  | `/v1/runs/{id}`               | Get run status, steps, and output        |
| `GET`  | `/v1/runs/{id}/events`        | Real-time SSE execution stream           |
| `POST` | `/v1/runs/{id}/cancel`        | Request graceful cancellation            |
| `POST` | `/v1/approvals/{id}`          | Approve/reject human-in-the-loop action  |

---

## 🤖 Supported Providers & Models

| Provider      | Models                                     | Status |
|---------------|--------------------------------------------|--------|
| **OpenAI**    | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`    | ✅ GA  |
| **Anthropic** | `claude-3.5-sonnet`, `claude-3-haiku`      | ✅ GA  |
| **Google**    | `gemini-1.5-pro`, `gemini-1.5-flash`       | 🔄 Beta|
| **Custom**    | Any OpenAI-compatible API                  | 🔧 DIY |

> **Provider Fallback**: Configure primary and secondary providers. If the primary fails, AIAgentX automatically routes to the fallback within the same capability class, protected by circuit breakers.

---

## 🚢 Deployment

### Docker Compose (Development)

```bash
docker compose up -d        # Start all services
docker compose logs -f app  # Follow application logs
```

### Kubernetes (Production)

AIAgentX ships with production-ready **Helm charts**:

```bash
# Deploy to your cluster
helm install aiagentx ./deploy/helm \
  --namespace aiagentx \
  --create-namespace \
  --values your-values.yaml
```

The Helm chart separates **stateless API pods** from **stateful worker pods**, with database migrations running as Kubernetes pre-upgrade jobs.

### Infrastructure Requirements

| Component  | Minimum        | Recommended        |
|------------|----------------|--------------------|
| PostgreSQL | 15+            | 16 (with RLS)     |
| Redis      | 7+             | 7+ (Alpine)       |
| CPU        | 2 cores        | 4+ cores           |
| Memory     | 2 GB           | 8+ GB              |

---

## 🧪 Testing

```bash
# Run all tests
./scripts/dev.sh test all

# Run only unit tests
./scripts/dev.sh test unit

# Run only integration tests
./scripts/dev.sh test integration

# Lint & type check
./scripts/dev.sh lint
./scripts/dev.sh format
```

### CI Pipeline

The GitHub Actions CI pipeline runs on every push and PR:

| Stage              | Tools                        | Description                           |
|--------------------|------------------------------|---------------------------------------|
| **Lint & Format**  | Ruff                         | Code style and import sorting         |
| **Type Check**     | MyPy (`strict = true`)       | Full static type analysis             |
| **Unit Tests**     | Pytest + PostgreSQL + Redis  | Tests against real service containers |
| **Integration**    | Pytest (PR only)             | End-to-end workflow validation        |
| **Security Scan**  | Bandit + Safety              | AST vulnerability + CVE scanning      |
| **Container Scan** | Docker + Trivy               | OS/library CVE analysis               |

---

## 🗺️ Roadmap

- [x] **Sprint 1** — Foundation: Clean architecture, domain entities, database layer
- [x] **Sprint 2** — Agent versioning lifecycle & CRUD API
- [x] **Sprint 3** — Tool security model & capability grants
- [ ] **Sprint 4** — Run execution engine with worker leases
- [ ] **Sprint 5** — Real-time SSE streaming & event system
- [ ] **Sprint 6** — Multi-tenant isolation with PostgreSQL RLS
- [ ] **Sprint 7** — Memory tiers (ephemeral, session, durable)
- [ ] **Sprint 8** — Cost budgeting & observability dashboards
- [ ] **Sprint 9** — Production hardening, Helm charts & documentation

---

## 🤝 Contributing

We love contributions! Whether it's bug fixes, new features, or documentation improvements — every contribution matters.

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/aiagentx.git
cd aiagentx

# 2. Create a feature branch
git checkout -b feat/amazing-feature

# 3. Install dependencies
./scripts/dev.sh setup

# 4. Make your changes and test
./scripts/dev.sh test all
./scripts/dev.sh lint

# 5. Commit and push
git commit -m "feat: add amazing feature"
git push origin feat/amazing-feature

# 6. Open a Pull Request 🚀
```

Please ensure your code passes all CI checks before submitting a PR.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ❤️ by the AIAgentX community</sub><br/>
  <sub>
    <a href="https://github.com/AIAgentX/aiagentx/issues">Report Bug</a> •
    <a href="https://github.com/AIAgentX/aiagentx/issues">Request Feature</a> •
    <a href="https://github.com/AIAgentX/aiagentx/discussions">Discussions</a>
  </sub>
</p>