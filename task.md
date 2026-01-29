# Tasks

## Consolidate Prompt Files
- [x] Update `CalcAgent/subagents.py` to import from `CalcAgent.config.prompts` <!-- id: 0 -->
- [x] Delete `CalcAgent/prompts/prompts.py` <!-- id: 1 -->
- [x] Remove empty `CalcAgent/prompts/` directory if applicable <!-- id: 2 -->

## Infrastructure Upgrade: Database & Backend
- [ ] Replace raw `sqlite3` queries with **SQLModel** (ORM) definitions <!-- id: 26 -->
- [ ] Model core entities: `User`, `Portfolio`, `Holdings`, `Transactions`, `ChatEntry`, `UserProfile`, `AuditLog` <!-- id: 27 -->
- [ ] Implement database migrations using Alembic <!-- id: 28 -->
- [ ] **Job Queue:** Design worker architecture using Celery or BullMQ/Redis <!-- id: 41 -->
- [ ] Implement background worker for heavy RAG processing and strategy backtesting <!-- id: 48 -->

## Intelligent Routing & Intent Detection (Bug Fix)
- [x] Implement a **Semantic Router** to classify intent (Logic vs. Stock vs. RAG) <!-- id: 29 -->
- [x] **Fix:** Fix hard bypass logic that routes company names to stock queries instead of RAG (api.py lines 163-170) <!-- id: 9 -->
- [x] Differentiate between "stock price of Apple" vs "What does Apple say in my document?" <!-- id: 10 -->
- [x] **Fix:** Prevent over-classification/timeout on vague or negative queries (e.g. "I don't have docs")

## Auto Trading Portfolio (Paper Trading)
- [ ] Design paper trading system architecture <!-- id: 12 -->
- [ ] Create portfolio model to track holdings, cash balance, and transactions <!-- id: 13 -->
- [ ] Implement agent-driven buy/sell logic (simulated trades) <!-- id: 14 -->
- [ ] Track portfolio performance over time (P&L, returns) <!-- id: 15 -->
- [ ] Build frontend UI to display portfolio and trade history <!-- id: 16 -->

## User Personalization & Risk Profiling
- [ ] Create `UserProfile` schema: `risk_tolerance`, `investment_horizon`, `goals` <!-- id: 42 -->
- [ ] Implement user settings UI to capture risk profile <!-- id: 49 -->
- [ ] Inject user profile context into Agent prompts for tailored advice <!-- id: 43 -->

## Notification System (The "Alert Loop")
- [ ] Implement Email notifications (SendGrid/Resend) for weekly summaries <!-- id: 44 -->
- [ ] Design logic for alerting on significant stock price movements <!-- id: 45 -->
- [ ] Implement Push/In-App alerts for trade executions <!-- id: 50 -->

## Integrate Finn Tech Project for Stock Research
- [x] Explore old Finn tech project to understand its structure <!-- id: 3 -->
- [x] Add article references to stock ticker graph section <!-- id: 4 -->
- [x] Enable users to access actual articles for market research <!-- id: 5 -->

## Real-Time Interaction (WebSockets)
- [x] Migrate chat endpoints from HTTP POST to **WebSockets** (Implemented via **SSE**) <!-- id: 30 -->
- [x] Implement streaming responses for "typing" effect <!-- id: 31 -->
- [ ] Enable real-time stock price and portfolio updates via socket events <!-- id: 32 -->

## RAG Knowledge Base Management
- [x] Create a **Document Manager** UI (List, Delete, View uploaded files) <!-- id: 33 -->
- [x] Scope uploaded documents/RAG data per user <!-- id: 8 -->
- [x] Implement logic to delete vector embeddings when a file is deleted <!-- id: 51 -->
- [x] Allow users to manage their context (delete old/irrelevant files) <!-- id: 34 -->

## Security, Compliance & Production Readiness
- [ ] **Urgent:** Make GitHub repository **Private** to protect IP and keys <!-- id: 38 -->
- [ ] **Monetization (Stripe):** Integrate Stripe for payment processing <!-- id: 39 -->
- [ ] Implement "Credit" purchasing flow and UI <!-- id: 52 -->
- [ ] **Credit System:** Database column `user_credits` + middleware deduction <!-- id: 40 -->
- [ ] **Tiered Rate Limiting:** Redis-backed (Free vs Pro limits) <!-- id: 35 -->
- [ ] **Audit Logs:** Immutable `AuditLog` table for all agent actions/trades <!-- id: 46 -->
- [x] **Data Isolation:** Ensure all DB queries are scoped by `user_id` from Auth token <!-- id: 6 -->
- [ ] **CORS & Headers:** Configure strict CORS for production and secure HTTP headers <!-- id: 36 -->
- [ ] **Input Validation:** Audit all Pydantic models to prevent injection/malformed data <!-- id: 37 -->
- [ ] **Legal Guardrails:** Add UI footer "Not Financial Advice" <!-- id: 47 -->
- [ ] **Legal Guardrails:** Update System Prompt with mandatory disclaimers <!-- id: 53 -->

## UI Enhancements: Stock Graph Overlay
- [ ] Allow users to select multiple stocks for comparison <!-- id: 17 -->
- [ ] Overlay selected stock graphs on a single chart <!-- id: 18 -->

## UI Enhancements: Output Formatting & Cleanup
- [x] Clean up raw agent text output for better readability <!-- id: 19 -->
- [x] Apply consistent markdown formatting (headers, bullets, tables) <!-- id: 20 -->
- [ ] Remove verbose/repetitive phrasing from responses <!-- id: 21 -->

## UI Enhancement: Persistent Chat History
- [x] Display previous questions and answers in the chat UI <!-- id: 22 -->
- [x] Load chat history on page load (from backend `/v1/agent/history`) <!-- id: 23 -->
- [x] Add visual separation between conversation sessions <!-- id: 24 -->
- [x] Consider sidebar or scrollable history panel for past conversations <!-- id: 25 -->
