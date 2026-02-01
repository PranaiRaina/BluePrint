# Tasks

## Infrastructure Upgrade: Database & Backend
- [ ] Replace raw `sqlite3` queries with **SQLModel** (ORM) definitions <!-- id: 26 -->
- [ ] Model core entities: `User`, `Portfolio`, `Holdings`, `Transactions`, `ChatEntry`, `UserProfile`, `AuditLog` <!-- id: 27 -->
- [ ] Implement database migrations using Alembic <!-- id: 28 -->
- [ ] **Job Queue:** Design worker architecture using Celery or BullMQ/Redis <!-- id: 41 -->
- [ ] Implement background worker for heavy RAG processing and strategy backtesting <!-- id: 48 -->

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


## Real-Time Interaction (WebSockets)
- [ ] Enable real-time stock price and portfolio updates via socket events <!-- id: 32 -->

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