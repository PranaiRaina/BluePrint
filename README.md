# BluePrint: Agentic Financial Intelligence

> **Empowering Financial Literacy through Autonomous AI Agents**

## 🚀 Mission: Democratizing Financial Intelligence
In a world where financial literacy is increasingly critical yet complex, **BluePrint** serves as your **Private, Intelligent Financial Officer**. By bridging the gap between raw data and actionable insights, we aim to solve the "Financial Literacy Crisis" at scale—without compromising your data sovereignty.

This is not just a chatbot—it's a **Privacy-First Agentic System** that understands, calculates, and researches on your behalf.

## 🔒 Privacy & Security: Your Data, Your Control
We believe financial data is the most sensitive data you own. **BluePrint** is built from the ground up to be a **Private Helper**:
- **Local-First Processing**: Your documents are processed in your own containerized environment.
- **Automatic Redaction**: We use **Microsoft Presidio** to detect and redact SSNs, Credit Card numbers, Names, and Phones *before* any data is stored.
- **Zero-Retention LLM Calls**: When we ask the AI a question, we only send the relevant snippets, and we use stateless calls.
- **Enterprise-Grade Isolation**: Your data lives in your `ChromaDB` instance, not on a public cloud vector store.

---

## 🌟 Key Features

### 1. 🧠 Intelligent Routing (Manager Agent)
The core **Manager Agent** acts as the central brain, intelligently analyzing user intent to route queries to the most specialized expert. It doesn't guess; it delegates.
- **Math/Logic** → Financial Calculator Agent
- **Market Data** → Stock Analyst Swarm
- **Personal Data** → Secure RAG Pipeline

### 2. 🛡️ Secure Personal Document Vault (RAG)
Upload invoices, tax documents, or statements with confidence.
- **Your Private Financial Brain**: Answers are generated from *your* documents, not public internet data.
- **Military-Grade Redaction**: Automatically detects and redacts PII (Personally Identifiable Information) like names, SSNs, and phones using **Microsoft Presidio** before data ever touches the vector database.
- **Contextual Search**: Uses **ChromaDB** to index your private data locally.

### 3. 📈 Autonomous Stock Analytics
A multi-agent swarm dedicated to market research:
- **Real-Time Data**: Integrated with **Finnhub** for live quotes and candle data.
- **Visual Analytics**: Dynamic, interactive charts powered by **Recharts**.
- **Deep Research**: Agents can browse the web (via **Tavily**) to cross-reference news with stock performance.

### 4. 🧮 Precision Financial Calculator
For when "close enough" isn't good enough.
- Powered by **Wolfram Alpha**, providing distinct, ground-truth answers for complex mortgage calculations, tax estimations, and investment projections.

---

## 🛠️ Technical Technology Stack

### Frontend (Client)
- **Framework**: React 18 + Vite (Fast & Light)
- **Language**: TypeScript (Type-safe reliability)
- **Styling**: Tailwind CSS + Framer Motion (Glassmorphic, premium UI)
- **Visualization**: Recharts (Financial charting)
- **Auth**: Supabase Auth (Secure JWT integration)

### Backend (Server)
- **API**: FastAPI (High-performance Async Python)
- **Runtime**: Uvicorn
- **Package Manager**: uv (Fast Python package installer)

### AI & Agentic Framework
- **Orchestration**: LangGraph (Stateful multi-agent workflows)
- **LLM**: Google Gemini 2.0 Flash (High speed, large context)
- **Tools**:
    - **Search**: Tavily Search API
    - **Math**: Wolfram Alpha
    - **Stocks**: Finnhub API
    - **Privacy**: Microsoft Presidio (PII Anonymization)

### Data Infrastructure (Dockerized)
- **Vector DB**: ChromaDB (For RAG document storage)
- **Time-Series DB**: TimescaleDB (PostgreSQL-based for financial data)
- **Caching**: Redis (Speed & Session management)
- **Storage**: Local filesystem (managed via Docker volumes)

---

## 🏗️ Architecture & Scalability

The system is designed as a **Microservices-ready** architecture, orchestrated via Docker Compose for easy reproduction and deployment.

### Development Workflow & Branching Strategy
This project followed a rigorous feature-branch workflow to ensure stability while adding complex agentic capabilities. Key branches included:
- **`main`**: Production-ready code.
- **`feature/rag-pipeline`**: Established the RAG system, introducing ChromaDB, Presidio (PII redaction), and the ingestion logic.
- **`persistent-memory-creation`**: Added SQLite-backed long-term memory to agents, allowing them to recall previous interactions across sessions.
- **`feature/stock-agents`**: Developed the dedicated stock analysis swarm (Quant Agent + Researcher Agent).

```text
[User (React UI)] <---> [Supabase Auth]
       |
       v
[FastAPI Gateway]
       |
       v
[Manager Agent (Router)] ----------------+--------------------------+
       |                                 |                          |
       v                                 v                          v
[Calc Agents (Wolfram)]          [RAG Pipeline]             [Stock Agent Swarm]
       |                                 |                          |
       |                        (PII Redaction)             +-------+--------+
       |                                 |                  |       |        |
       v                                 v                  v       v        v
(Wolfram LLM API)                 [ChromaDB]         [Finnhub]    [Quant] [Tavily]
                                                 (TimescaleDB)    (Agent)  (Agent)
```

### Architecture Deep Dive
1.  **The "Router" Pattern (Manager Agent)**: Instead of a single LLM trying to do everything, the `ManagerAgent` is a specialized classifier. It intercepts every user query and routes it to the *best* tool for the job. This reduces hallucinations (by not asking a generalist model to do math) and improves speed.
2.  **Privacy-by-Design**: Usage of **Microsoft Presidio** ensures that no Sensitive PII (Personally Identifiable Information) is ever stored in our Vector Database (`ChromaDB`). This is critical for financial applications.
3.  **Hybrid Storage Model**:
    - **Vector (ChromaDB)**: For unstructured text (invoices, docs).
    - **Time-Series (TimescaleDB)**: For structured, high-frequency stock data.
    - **Relational (SQLite)**: For agent conversational memory.

### 🧩 Agent Specific Architectures

#### 1. 🧮 CalcAgent (Financial Specialist)
- **Role**: Deterministic calculation engine.
- **Trigger**: Activated by queries involving numbers, "calculate", "mortgage", "tax", or "future value".
- **Tooling**: Direct integration with **Wolfram Alpha LLM API**.
- **Workflow**:
    1.  User Query: "What is the monthly payment on a $500k mortgage at 6%?"
    2.  Manager Handover -> CalcAgent.
    3.  CalcAgent converts natural language to Wolfram syntax.
    4.  Wolfram executes logic (Physics/Math engine).
    5.  Result returned verbatim to user (No hallucination risk).

#### 2. 📄 RAG Pipeline (Document Intelligence)
- **Role**: Private Context Provider.
- **Ingestion Flow**:
    1.  **Upload**: User uploads PDF via Frontend.
    2.  **PII Scrubbing**: `PresidioAnalyzer` scans for Phone Numbers, SSNs, and Names. `PresidioAnonymizer` replaces them with `<REDACTED>`.
    3.  **Summarization**: Generates a 2-sentence "global context" summary of the doc.
    4.  **Vectorization**: Chunks text (1000 chars) and embeds using `GoogleGenerativeAIEmbeddings`.
    5.  **Storage**: Metadata + Vectors saved to ChromaDB.
- **Retrieval Flow**:
    1.  Query -> Similarity Search (k=4, Threshold=0.35).
    2.  Context Stuffing -> LLM (Gemini 2.0).
    3.  Citation -> Answer with source document reference.

#### 3. 📈 StockAgent Swarm (Market Intelligence)
- **Role**: Real-time market analysis.
- **Architecture**: A mini-swarm of two sub-agents:
    - **Researcher Agent**: Uses `Tavily` to find latest news (e.g., "Why is NVDA down today?").
    - **Quant Agent**: Uses `Finnhub` to pull price, candles, and RSI.
- **Visualization**: Returns a specialized JSON payload that the React Frontend parses to render **Interactive Charts** (Candlestick/Line) dynamically.


### Business Impact & Scale
- **Privacy as a Service**: In an era of data leaks, a "Private Financial Officer" that keeps data local is a massive differentiator.
- **Scalability**: Stateless API design allows horizontal scaling of agent nodes.
- **Market Fit**: Fills the void between simple expense trackers and expensive human advisors.
- **Trust Architecture**: The code is open, the redaction is visible, and the storage is local.

---

## 📦 Getting Started

### Prerequisites
- Docker Desktop
- API Keys (Google Gemini, Finnhub, Tavily, Wolfram, Supabase)

### Installation
1.  **Clone & Configure**:
    ```bash
    git clone https://github.com/PranaiRaina/RoseHacks2026.git
    cd RoseHacks2026
    # Add your keys to .env
    ```

2.  **Run with Docker**:
    The entire system (Frontend, Backend, Databases) is containerized.
    ```bash
    docker-compose up --build -d
    ```

3.  **Access**:
    - **Frontend**: http://localhost:3000
    - **Backend API**: http://localhost:8001/docs

---

### 🔍 Learning Points
- **Agentic Design**: Moving beyond "chatbots" to "systems that do things".
- **Hybrid Storage**: Combining Vector stores (semantic search) with structured SQL (Timescale) and Key-Value (Redis).
- **Secure By Design**: Integrating PII redaction at the ingestion layer ensures privacy isn't an afterthought.

## 📂 Codebase Layout

An overview of the project structure and key files:

```text
├── Auth/                   # Authentication & Verification Logic
│   ├── verification.py     # Supabase JWT token validation
│   └── dependencies.py     # FastAPI dependency injection for Auth
│
├── CalcAgent/              # Financial Calculation Agent
│   ├── agent.py            # Main Agent Definition
│   ├── tools/wolfram.py    # Wolfram Alpha Integration
│   └── config/             # Prompts and LLM Configuration
│
├── ManagerAgent/           # Core Router & API Gateway
│   ├── api.py              # FastAPI Endpoints (Entry Point)
│   ├── router.py           # Logic to route queries to specialized agents
│   └── tools.py            # Wrappers for calling RAG/Stock tools
│
├── RAG_PIPELINE/           # Document Ingestion & Retrieval
│   ├── src/
│   │   ├── ingestion.py    # PDF Processing, PII Redaction, Chunking
│   │   └── graph.py        # LangGraph Retrieval Workflow
│   └── ...
│
├── StockAgents/            # Multi-Agent Stock Market Swarm
│   └── backend/services/
│       ├── agent_engine.py      # Coordinator for Quant/Researcher agents
│       ├── quant_agent.py       # Technical Analysis Logic
│       ├── researcher_agent.py  # News/Sentiment Logic
│       └── finnhub_client.py    # Market Data Connector
│
├── frontend/               # React + Vite Web Application
│   ├── src/
│   │   ├── components/     # UI Components (UploadZone, StockAnalyticsView)
│   │   ├── pages/          # Route Pages (Dashboard, Auth, Landing)
│   │   ├── services/       # API Integration (agent.ts)
│   │   └── lib/            # Utilities (supabase.ts)
│   └── Dockerfile          # Frontend container config
│
├── docker-compose.yml      # Multi-container orchestration config
├── requirements.lock       # Pinnned Python dependencies
└── scripts/                # Utility scripts (testing, key validation)
```

---

*Built for RoseHack 2026. Transforming financial anxiety into financial agency.*
