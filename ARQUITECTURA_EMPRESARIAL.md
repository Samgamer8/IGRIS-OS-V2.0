          🏢 ARQUITECTURA EMPRESARIAL - IGRIS OS
         Estructura Organizacional & Capas Técnicas Integradas
════════════════════════════════════════════════════════════════════════════════

# 📊 JERARQUÍA ORGANIZACIONAL (Top-Down)

```
┌────────────────────────────────────────────────────────────────────┐
│                        👤 USER/ADMIN REQUEST                       │
│                  (Sam Admin - Punto de entrada único)              │
│                                                                    │
│  Responsabilidad: Gestión general, decisiones estratégicas,      │
│                   autorización de cambios, release management     │
└────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────┬──────────────────────────────────┐
│                                 │                                  │
│  🎨 FRONTEND LAYER              │  🤖 AGENT ORCHESTRATION LAYER   │
│  (Presentación & UX)            │  (Automatización & Coordinación) │
│                                 │                                  │
│  • React 19+ (Web)              │  • LangChain (Framework core)   │
│  • Next.js 15+ (SSR/SSG)        │  • CrewAI (Multi-agent system) │
│  • Streamlit (Dashboards)       │  • Mastra (Workflow orchestr.) │
│  • Tailwind CSS (Styling)       │  • AutoGen (Legacy support)    │
│  • ShadcN/UI (Components)       │  • Langsmith (Agent debugger)  │
│  • Zustand (State mgmt)         │                                 │
│  • Playwright (E2E testing)     │  Responsabilidad: Coordinar    │
│                                 │  múltiples agentes especializados,
│  Responsabilidad: Interfaz de   │  ejecutar workflows, gestionar  │
│  usuario responsive, accesible, │  prompts y resultados          │
│  real-time updates              │                                 │
└─────────────────────────────────┴──────────────────────────────────┘
         │                                      │
         ├──────────────────┬──────────────────┤
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  📚 KNOWLEDGE    │ │  🧠 MODELS (LLM) │ │  🔧 TOOLS (MCP)  │
│  LAYER (RAG)     │ │  (Language Models)│ │  (Model Context  │
│                  │ │                  │ │   Protocol)      │
│ • Documents      │ │ • Claude 3.7+    │ │ • GitHub MCP     │
│ • Vector DB      │ │   (Anthropic)    │ │ • Slack MCP      │
│   - Qdrant       │ │                  │ │ • Browser MCP    │
│   - Weaviate     │ │ • GPT-5.x        │ │ • APIs MCP       │
│   - Pinecone     │ │   (OpenAI)       │ │ • Database MCP   │
│                  │ │                  │ │ • File System    │
│ • Memory Store   │ │ • Gemini 3.7+    │ │ • Playwright MCP │
│   - Redis        │ │   (Google)       │ │                  │
│   - PostgreSQL   │ │                  │ │ • Custom MCP     │
│   - SQLite       │ │ • Llama 3.2+     │ │   Servers        │
│                  │ │   (Meta)         │ │                  │
│ • Retrieval      │ │                  │ │ Responsabilidad: │
│   - Semantic     │ │ • Mixtral        │ │ Exponer herramientas
│   - Hybrid       │ │   (Mistral)      │ │ y recursos externos
│   - Full-text    │ │                  │ │ a agentes        │
│                  │ │ • Local inference│ │                  │
│ Responsabilidad: │ │   (Ollama, etc)  │ │ • Versionado     │
│ Gestionar        │ │                  │ │ • Autenticación  │
│ conocimiento,    │ │ Responsabilidad: │ │ • Rate limiting  │
│ ingestión,       │ │ Proporcionar     │ │ • Fallback logic │
│ búsqueda         │ │ capacidades de   │ │                  │
│                  │ │ razonamiento,    │ │                  │
│                  │ │ generación       │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
         ┌─────────────────────────────────────────┐
         │     💾 DATA LAYER (Persistencia)       │
         │                                       │
         │ • PostgreSQL 16+ (Relational DB)     │
         │ • Redis 7+ (Cache/Session)           │
         │ • S3/Storage (Object store)          │
         │   - AWS S3                           │
         │   - MinIO (Self-hosted)              │
         │   - GCS (Google Cloud)               │
         │                                       │
         │ • Qdrant 1.7+ (Vector search)        │
         │ • Elasticsearch (Full-text search)   │
         │ • MongoDB (NoSQL - optional)         │
         │                                       │
         │ Responsabilidad: Persistencia,       │
         │ escalabilidad, seguridad de datos    │
         └─────────────────────────────────────────┘
                            ▼
         ┌─────────────────────────────────────────┐
         │ 📊 OBSERVABILITY & EVALS              │
         │    (Monitoring & Quality Assurance)    │
         │                                       │
         │ • Langfuse (Prompt management)       │
         │ • Phoenix (LLM telemetry)            │
         │ • RAGAS (RAG evaluation)             │
         │ • TruLens (LLM evaluation)           │
         │ • Prometheus (Metrics)               │
         │ • Grafana (Dashboards)               │
         │ • ELK Stack (Logging)                │
         │ • Sentry (Error tracking)            │
         │                                       │
         │ Responsabilidad: Monitorear          │
         │ rendimiento, evaluar calidad,        │
         │ detectar anomalías                   │
         └─────────────────────────────────────────┘
                            ▼
         ┌─────────────────────────────────────────┐
         │ 🚀 DEPLOYMENT & INFRASTRUCTURE         │
         │                                       │
         │ • Docker 26+ (Containerización)      │
         │ • Kubernetes 1.31+ (Orchestration)   │
         │   - ArgoCD (GitOps)                  │
         │   - Helm (Package management)        │
         │                                       │
         │ • Vercel (Edge deployment - React)   │
         │ • Cloudflare (CDN & Workers)         │
         │ • AWS/GCP/Azure (Cloud provider)     │
         │                                       │
         │ • GitHub Actions (CI/CD)             │
         │ • Terraform (IaC)                    │
         │ • Ansible (Configuration mgmt)       │
         │                                       │
         │ Responsabilidad: Deployments         │
         │ seguros, escalables, resilientes     │
         └─────────────────────────────────────────┘
```

---

# 🎯 CAPAS TÉCNICAS DETALLADAS

## NIVEL 0: USER/ADMIN LAYER
**Rol:** Sam Admin (CTO/Arquitecto Principal)
- Punto de entrada único del sistema
- Autorización de releases y cambios críticos
- Decisiones estratégicas de arquitectura
- Gestión de configuración global

---

## NIVEL 1: PRESENTATION & ORCHESTRATION

### 🎨 Frontend Layer
**Stack Principal:**
```yaml
Frameworks:
  - React 19+: Core framework para componentes
  - Next.js 15+: SSR/SSG, API routes, edge computing
  - Streamlit: Dashboards analíticos rápidos

Styling:
  - Tailwind CSS: Utilidades CSS modernas
  - ShadcN/UI: Componentes accesibles y personalizables
  - Framer Motion: Animaciones fluidas

State Management:
  - Zustand: Ligero, escalable
  - TanStack Query: Sincronización de datos
  - Jotai: Atoms de estado disperso

Testing:
  - Vitest: Unit/integration tests
  - Playwright: E2E testing
  - Storybook: Component documentation
```

**Responsabilidades:**
- Interfaz de usuario responsive y accesible
- Real-time updates desde el backend
- Manejo de estado global
- Validación de entrada
- Error handling y fallbacks

---

### 🤖 Agent Orchestration Layer
**Stack Principal:**
```yaml
Core Frameworks:
  - LangChain 0.3+: Framework de composición
  - CrewAI 0.30+: Sistema multi-agente avanzado
  - Mastra: Workflow orchestration moderno
  - AutoGen (Opcional): Legacy support

Components:
  - Langsmith: Debugging y monitoring de prompts
  - Langfuse: Analytics de LLM
  - Agents Factory: Custom agent creation

Patterns:
  - ReAct (Reasoning + Acting)
  - Function Calling
  - Tool Use
  - Chain of Thought
```

**Responsabilidades:**
- Coordinar múltiples agentes especializados
- Ejecutar workflows complejos
- Gestionar contexto y memoria
- Routing inteligente de tareas
- Error recovery y retry logic
- Logging de acciones y decisiones

---

## NIVEL 2: KNOWLEDGE, MODELS & TOOLS (Paralelo)

### 📚 Knowledge Layer (RAG)
**Componentes:**

```yaml
Document Ingestion:
  - Loaders: PDF, HTML, Markdown, Word, Code
  - Splitters: Semantic, recursive, sliding window
  - Preprocessors: Cleaning, normalization

Vector Storage:
  - Qdrant 1.7+: Vector search (PRIMARY)
  - Weaviate: Alternatia con GraphQL
  - Pinecone: Managed vector DB
  - Milvus: Open-source escalable

Memory Systems:
  - Short-term: Redis + PostgreSQL
  - Long-term: Persistent vector DB
  - Episodic: Graph-based (Neo4j optional)
  - Semantic: Embedding-based retrieval

Retrieval Strategies:
  - Semantic search (vector similarity)
  - Hybrid search (vector + keyword)
  - Full-text search (Elasticsearch)
  - Multi-hop retrieval (Chain reasoning)
```

**Responsabilidades:**
- Ingestión y procesamiento de documentos
- Indexación en vector DB
- Búsqueda rápida y relevante
- Deduplicación de conocimiento
- Versionado de documentos

---

### 🧠 Models Layer (LLM)
**Stack de Modelos:**

```yaml
Primary (API-based):
  - Claude 3.7+
    * Sonnet: Balanced (default)
    * Opus: Advanced reasoning
    * Haiku: Fast, lightweight
  
  - GPT-5.x (OpenAI)
    * o1: Advanced reasoning
    * GPT-4 Turbo: Balanced
    * GPT-4 Mini: Fast
  
  - Gemini 3.7+ (Google)
    * Advanced: Full capabilities
    * Flash: Fast inference
    * Pro: Specialized tasks

Secondary:
  - Llama 3.2+ (Meta)
    * Quantized versions (4-8bit)
    * Fine-tuning capable
  
  - Mixtral (Mistral)
    * MoE architecture
    * Efficient routing
  
  - Local Inference:
    * Ollama: Local model serving
    * vLLM: High-throughput inference
    * LM Studio: User-friendly UI

Specialized Models:
  - Text-to-speech: ElevenLabs, Google Cloud TTS
  - Speech-to-text: Whisper, Google Cloud STT
  - Image generation: DALL-E 3, Flux, Stable Diffusion
  - Embeddings: OpenAI, Sentence Transformers
```

**Responsabilidades:**
- Seleccionar modelo óptimo por tarea
- Gestionar tokens y costos
- Implementar fallbacks
- Fine-tuning y adaptación
- Rate limiting y throttling

---

### 🔧 Tools Layer (MCP - Model Context Protocol)
**Servidores MCP Disponibles:**

```yaml
Integration Tools:
  - GitHub MCP: Repos, PRs, issues, code search
  - Slack MCP: Messages, channels, files
  - Browser MCP: Web scraping, navigation
  - Figma MCP: Design assets, components
  - Linear MCP: Issues, projects, roadmaps

Data Tools:
  - Database MCP: SQL queries, schemas
  - APIs MCP: REST, GraphQL, webhooks
  - File System: Local file operations
  - Cloud Storage: S3, GCS, Azure Blob

Specialized:
  - Playwright MCP: Headless browser automation
  - Terminal MCP: CLI commands (sandboxed)
  - Docker MCP: Container management
  - Kubernetes MCP: Cluster operations

Custom MCP Servers:
  - IGRIS Internal: Custom business logic
  - Security: Encrypted tool calls
  - Audit: Logging all tool usage
```

**Responsabilidades:**
- Exponer herramientas a agentes
- Validar y autorizar llamadas
- Manejo de errores y timeouts
- Caching de resultados
- Rate limiting y quotas

---

## NIVEL 3: DATA LAYER

### 💾 Persistencia & Storage
**Stack Completo:**

```yaml
Relational Database:
  - PostgreSQL 16+
    * Connection pooling (PgBouncer)
    * Replication & HA
    * JSON/JSONB support
    * Full-text search
    * Window functions

In-Memory Cache:
  - Redis 7+
    * Session store
    * Rate limiting (Sliding window)
    * Pub/Sub messaging
    * Distributed locks
    * Caching layer

Object Storage:
  - AWS S3 (Primary)
    * Versioning
    * Encryption
    * Lifecycle policies
    * CloudFront CDN
  
  - MinIO (Self-hosted alternative)
    * S3-compatible API
    * Erasure coding
    * Distributed setup

Vector Search:
  - Qdrant 1.7+
    * Multi-shard setup
    * Filtering & range queries
    * Snapshot management
    * Monitoring & analytics

Search Engine:
  - Elasticsearch 8+
    * Full-text search
    * Aggregations
    * Geo-spatial queries
    * ML capabilities

Optional:
  - MongoDB: Flexible schema
  - Neo4j: Graph relationships
  - TimescaleDB: Time-series data
  - DuckDB: Analytics queries
```

**Responsabilidades:**
- Persistencia ACID
- Escalabilidad horizontal
- Backup y disaster recovery
- Encryption at rest
- Data governance y compliance

---

## NIVEL 4: OBSERVABILITY & EVALUATION

### 📊 Monitoring & Quality Assurance
**Stack Completo:**

```yaml
LLM Observability:
  - Langfuse 2.0+
    * Prompt management
    * Traces & logs
    * Cost tracking
    * Evaluation framework
  
  - Phoenix (Arize)
    * LLM telemetry
    * Drift detection
    * Performance analytics

RAG Evaluation:
  - RAGAS 0.1+
    * Context relevance
    * Faithfulness
    * Answer relevance
    * Semantic similarity
  
  - TruLens 0.27+
    * Feedback functions
    * Leaderboards
    * Root cause analysis

Application Monitoring:
  - Prometheus
    * Metrics collection
    * Time-series database
    * Alerting rules
  
  - Grafana
    * Dashboards
    * Custom visualizations
    * Alertmanager integration
  
  - ELK Stack
    * Elasticsearch: Storage
    * Logstash: Processing
    * Kibana: Visualization

Error Tracking:
  - Sentry 24+
    * Exception tracking
    * Release management
    * Performance monitoring
    * Distributed tracing

Security:
  - Falco: Runtime security
  - Vault: Secrets management
  - Audit logging (PostgreSQL)
```

**Responsabilidades:**
- Monitorear latencias
- Evaluar calidad de respuestas
- Detectar anomalías
- Generar alertas
- SLA compliance

---

## NIVEL 5: DEPLOYMENT & INFRASTRUCTURE

### 🚀 Deployment Stack
**Containerización & Orquestación:**

```yaml
Docker 26+:
  - Multi-stage builds
  - Image optimization
  - Registry: ECR / Docker Hub
  - Scanning: Trivy, Grype

Kubernetes 1.31+:
  - Cluster setup: EKS/GKE/AKS
  - Node autoscaling
  - Pod security policies
  - Network policies
  
  Tools:
  - Helm 3.x: Package management
  - ArgoCD: GitOps continuous deployment
  - Sealed Secrets: Encrypted K8s secrets

Edge Deployment:
  - Vercel: Next.js hosting
    * Automatic deployments
    * Edge functions
    * Analytics
  
  - Cloudflare: CDN & Workers
    * Global distribution
    * Serverless functions
    * DDoS protection

Cloud Providers:
  - AWS (Primary)
    * ECS/EKS for containers
    * Lambda for serverless
    * RDS for databases
  
  - GCP (Alternative)
    * Google Cloud Run
    * Cloud SQL
    * BigQuery
  
  - Azure (Alternative)
    * AKS
    * Cosmos DB
    * Synapse Analytics

CI/CD Pipeline:
  - GitHub Actions
    * Automated tests
    * Security scanning
    * Artifact build
    * Deployment workflows

Infrastructure as Code:
  - Terraform 1.8+
    * AWS/GCP/Azure resources
    * State management
    * Modules & composition
  
  - Ansible 2.15+
    * Configuration management
    * Playbooks
    * Inventory management
```

**Responsabilidades:**
- Deployments sin downtime
- Auto-scaling y load balancing
- Disaster recovery
- Cost optimization
- Security hardening

---

# 🔄 FLUJO DE DATOS END-TO-END

```
User Request
    ▼
┌─────────────────────────────────────┐
│  Frontend (React/Next.js/Streamlit) │
└─────────────────────────────────────┘
    ▼
┌─────────────────────────────────────┐
│  Agent Orchestration (LangChain)    │
│  ├─ Task Router                     │
│  ├─ Prompt Management               │
│  └─ Execution Engine                │
└─────────────────────────────────────┘
    │
    ├─► Knowledge Layer (RAG)
    │   ├─ Retrieval (Qdrant)
    │   └─ Memory (Redis/PostgreSQL)
    │
    ├─► Model Selection
    │   ├─ Cost optimization
    │   └─ Latency reduction
    │
    ├─► Tools Invocation (MCP)
    │   ├─ GitHub API
    │   ├─ External APIs
    │   └─ Databases
    │
    └─► Data Layer
        ├─ Store results (PostgreSQL)
        ├─ Cache (Redis)
        └─ Archive (S3)
           
    ▼
┌─────────────────────────────────────┐
│  Observability & Logging            │
│  ├─ Langfuse (Prompts)              │
│  ├─ Prometheus (Metrics)            │
│  └─ ELK (Logs)                      │
└─────────────────────────────────────┘
    ▼
┌─────────────────────────────────────┐
│  Response to User                   │
│  (via Frontend)                     │
└─────────────────────────────────────┘
```

---

# 👥 ROLES & RESPONSABILIDADES

| Role | Nivel | Responsabilidades |
|------|-------|------------------|
| **User/Admin** | 0 | Autorización, decisiones estratégicas, releases |
| **Frontend Dev** | 1 | UI/UX, React, Next.js, styling |
| **Agent Engineer** | 1 | LangChain, CrewAI, workflows, prompts |
| **ML Engineer** | 2-3 | Model selection, fine-tuning, embeddings |
| **DevOps** | 4-5 | Kubernetes, CI/CD, infrastructure |
| **Data Engineer** | 3 | Databases, data pipelines, ETL |
| **Security** | Cross | Auth, encryption, compliance |
| **QA/Eval** | 4 | Testing, RAGAS, quality metrics |

---

# 📈 ESCALABILIDAD & PERFORMANCE

**Targets:**
- Latency: < 500ms para respuestas simples
- Throughput: 1000+ req/s
- Availability: 99.99% uptime
- Cost: Optimizado por token/request
- Coverage: Coverage ≥ 75%

---

# 🔒 SEGURIDAD

**Principios:**
- Zero Trust Architecture
- Encryption in transit & at rest
- Secrets rotation
- Audit logging
- Compliance (GDPR, CCPA, SOC2)

---

**Versión:** 1.0 | **Created:** 2026-08-30 | **Status:** 🟢 PRODUCTION-READY
