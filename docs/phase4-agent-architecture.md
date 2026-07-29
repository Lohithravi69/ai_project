# Phase 4: Multi-Agent Reasoning Architecture

## Objective

Transform the system from a tool-execution engine into an autonomous AI software
engineering platform with multi-agent reasoning. Every agent routes through the
existing Phase 3 Tool Layer — no direct repository modifications.

## Architecture Constraint

Phase 3 infrastructure is **frozen**:
- No new databases
- No new frameworks
- No new external services
- No replacing existing components

Every Phase 4 feature builds **on top of** what exists.

---

## Agent Pipeline

```
User Request
     │
     ▼
 Planner Agent ─────────────────────────► Execution Pipeline (Phase 3)
     │                                              │
     ▼                                              │
 Architect Agent                                    │
     │                                              │
     ▼                                              │
 Task Decomposer                                    │
     │                                              │
     ▼                                              │
   ┌─── Coding Agent ────────┐                      │
   │   Reviewer Agent ◄──────┤                      │
   │   Testing Agent  ◄──────┤                      │
   │   Debug Agent    ◄──────┘                      │
   │   Documentation Agent                          │
   └──────────┬─────────────────────────────────────┘
              ▼
   Execution Pipeline (Phase 3)
```

All agents communicate through a shared **AgentContext** object. No agent
modifies files directly — they produce `ToolRunRequest` objects that feed into
the Phase 3 execution pipeline.

---

## Agent Responsibilities

### 1. Planner Agent
- **Input**: Free-form user request (text, issue reference, PR description)
- **Output**: Decomposed high-level plan with objective, reasoning, scope
- **Storage**: Creates an `ExecutionPlanRecord` (table exists)
- **Tool access**: Read-only (ReadFile, SearchRepository, ListFiles, QueryVectorStore)
- **Reasoning**: Produces `AIReasoning` explaining request interpretation

### 2. Architect Agent
- **Input**: Planner's high-level plan
- **Output**: Technical design — files to create/modify, data flow, interfaces
- **Tool access**: Read-only (ReadFile, SearchRepository, GitDiff)
- **Reasoning**: Explains architectural choices and alternatives considered

### 3. Task Decomposer
- **Input**: Architectural design
- **Output**: Ordered list of concrete `ToolRunRequest` objects
- **Storage**: Updates `ExecutionPlanRecord.execution_order_json`
- **Tool access**: Read-only (ListFiles, ReadFile, SearchRepository)
- **Reasoning**: Explains task breakdown and ordering rationale

### 4. Coding Agent
- **Input**: One or more `ToolRunRequest` objects
- **Output**: File changes via Phase 3 tools (WriteFile, CreateFile, etc.)
- **Tool access**: Read + Write (ReadFile, WriteFile, CreateFile, DeleteFile, MoveFile)
- **Reasoning**: Explains implementation decisions, edge cases handled

### 5. Reviewer Agent
- **Input**: Code produced by Coding Agent (via diff_preview)
- **Output**: Review comments, approval/rejection, suggested changes
- **Tool access**: Read-only (ReadFile, GitDiff, SearchRepository)
- **Reasoning**: Explains review findings, severity, and recommendations

### 6. Testing Agent
- **Input**: Modified code, test files
- **Output**: Test execution results, new test files
- **Tool access**: Read + Write (CreateFile, WriteFile, RunPyTest, RunPlaywright)
- **Reasoning**: Explains test coverage decisions and edge cases

### 7. Debug Agent
- **Input**: Test failure output, error logs
- **Output**: Root cause analysis, fix suggestions
- **Tool access**: Read-only (ReadFile, ReadLogs, SearchRepository, GitDiff)
- **Reasoning**: Explains failure analysis and proposed fix

### 8. Documentation Agent
- **Input**: Final code changes
- **Output**: Updated documentation, changelog entries, inline comments
- **Tool access**: Write (WriteFile, CreateFile, ReadFile)
- **Reasoning**: Explains documentation decisions

---

## Agent Communication Protocol

All agents exchange data through a single shared structure:

```python
class AgentContext(BaseModel):
    execution_id: str
    plan_id: str | None = None
    user_request: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    architecture: dict[str, Any] = Field(default_factory=dict)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    current_tool_requests: list[ToolRunRequest] = Field(default_factory=list)
    tool_responses: list[ToolRunResponse] = Field(default_factory=list)
    review_feedback: list[dict[str, Any]] = Field(default_factory=list)
    agent_trace: list[AgentTraceEntry] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
```

### Agent Trace Entry

Every agent decision is recorded for full observability:

```python
class AgentTraceEntry(BaseModel):
    agent_name: str
    started_at: datetime
    finished_at: datetime | None = None
    input_summary: str = ""
    output_summary: str = ""
    tool_calls: int = 0
    ai_reasoning: AIReasoning = Field(default_factory=AIReasoning)
    duration_ms: int = 0
    success: bool = True
    error: str = ""
```

---

## Shared Agent Base Class

All agents inherit from a common `BaseAgent`:

```python
class BaseAgent(ABC):
    name: str
    description: str

    def __init__(self, session: AsyncSession, context: AgentContext):
        self.session = session
        self.context = context
        self.registry = ToolRegistry()
        self.metrics = MetricsCollector()

    @abstractmethod
    async def run(self) -> AgentContext:
        ...

    async def use_tool(self, request: ToolRunRequest) -> ToolRunResponse:
        """Route through Phase 3 Execution Manager."""
        manager = ExecutionManager(self.session)
        response = await manager.run_tool(request)
        self.context.tool_responses.append(response)
        self.context.current_tool_requests.append(request)
        return response

    async def dry_run_tool(self, request: ToolRunRequest) -> ToolRunResponse:
        """Dry-run a tool without executing."""
        request.dry_run = True
        return await self.use_tool(request)

    def record_reasoning(
        self,
        reasoning: str,
        alternatives: list[str] | None = None,
        why: str = "",
        confidence: float = 0.0,
        risks: list[str] | None = None,
    ) -> AIReasoning:
        ai_reasoning = AIReasoning(
            reasoning=reasoning,
            alternatives_considered=alternatives or [],
            why_this_choice=why,
            confidence=confidence,
            expected_risks=risks or [],
        )
        self.context.agent_trace.append(AgentTraceEntry(
            agent_name=self.name,
            started_at=datetime.now(timezone.utc),
            ai_reasoning=ai_reasoning,
        ))
        return ai_reasoning
```

---

## Data Flow (End-to-End Example)

```
1. User: "Add authentication to the login page"

2. Planner Agent
   ├─ Reads project structure (ReadFile, ListFiles)
   ├─ Produces plan: "Add auth middleware, login form, session handler"
   ├─ AIReasoning: {confidence: 0.92, alternatives: ["JWT", "OAuth", "Session"], why_this_choice: "JWT best matches existing stack"}
   └─ Stores: ExecutionPlanRecord with ai_reasoning_json

3. Architect Agent
   ├─ Reads existing auth files (ReadFile, SearchRepository)
   ├─ Produces design: files to create/modify, data flow diagram
   ├─ AIReasoning: explains component placement, dependency
   └─ Updates: plan_json with architecture section

4. Task Decomposer
   ├─ Breaks design into ordered ToolRunRequest list
   ├─ Order: CreateFile(middleware.py) → WriteFile(login.py) → ...
   └─ Updates: execution_order_json with sequenced tasks

5. Coding Agent
   ├─ For each task: dry_run → execute → checkpoint
   ├─ Creates middleware.py, modifies login.py, updates routes
   ├─ AIReasoning: explains each implementation decision
   └─ Each call routes through ExecutionManager

6. Reviewer Agent
   ├─ Reads created files (ReadFile, GitDiff)
   ├─ Reviews code quality, security, style
   ├─ AIReasoning: flags potential issues, suggests improvements
   └─ Returns review: approve / changes-requested

7. Testing Agent
   ├─ Creates test_auth.py (CreateFile)
   ├─ Runs pytest (RunPyTest)
   ├─ AIReasoning: explains test coverage
   └─ Returns test results

8. Debug Agent (only if tests fail)
   ├─ Reads test output (ReadFile, ReadLogs)
   ├─ Identifies root cause
   ├─ AIReasoning: explains failure chain
   └─ Suggests fix → Coding Agent re-runs

9. Documentation Agent
   ├─ Reads final files (ReadFile)
   ├─ Updates README, API docs (WriteFile)
   ├─ AIReasoning: explains doc structure
   └─ Finalizes changes
```

---

## Storage (Existing Tables Reused)

| Concept | Existing Table | New Fields Needed |
|---------|---------------|-------------------|
| Execution plan | `execution_plans` | `ai_reasoning_json` (exists) |
| Tool calls | `tool_executions` | none |
| Checkpoints | `checkpoints` | none |
| Rollbacks | `rollback_history` | none |
| Workspaces | `workspaces` | none |
| Agent execution | `agent_executions` | exists from Phase 2 |

One small extension to `ExecutionPlanRecord`:

```
agent_trace_json: JSON field storing list[AgentTraceEntry]
architecture_json: JSON field storing architect's design output
agent_status: String tracking which agent is currently active
```

No new ORM tables required — everything fits in JSON columns on existing rows.

---

## API v5 Router

New endpoints under `/api/v5/`:

```
POST /api/v5/agents/run
  Body: { request_text, repository_id, mode: "full" | "plan-only" | "code-only" }
  Response: { execution_id, plan_id, results, trace }

GET  /api/v5/agents/{execution_id}/trace
  Response: { agent_trace: [AgentTraceEntry, ...] }

GET  /api/v5/agents/{execution_id}/status
  Response: { status, current_agent, progress }
```

The v5 router adds no new infrastructure — it reuses the existing `get_session`
dependency and the existing `AsyncSession`.

---

## Implementation Plan

### Step 1: Base Agent Infrastructure
- Create `backend/agents/base.py` — `BaseAgent`, `AgentContext`, `AgentTraceEntry`
- Create `backend/agents/types.py` — Enum of agent types, agent registry
- Extend `ExecutionPlanRecord` with `agent_trace_json`, `architecture_json`, `agent_status`

### Step 2: Planner Agent
- Create `backend/agents/planner.py` — `PlannerAgent(BaseAgent)`
- Reads user request, creates `ExecutionPlanRecord`
- Produces `AIReasoning` with plan rationale

### Step 3: Architect Agent
- Create `backend/agents/architect.py` — `ArchitectAgent(BaseAgent)`
- Reads existing codebase, produces design specification
- Updates `ExecutionPlanRecord.architecture_json`

### Step 4: Task Decomposer
- Create `backend/agents/decomposer.py` — `TaskDecomposer(BaseAgent)`
- Breaks architecture into ordered `ToolRunRequest` sequence
- Updates `execution_order_json`

### Step 5: Coding Agent
- Create `backend/agents/coder.py` — `CodingAgent(BaseAgent)`
- Iterates tasks, calls Phase 3 tools, handles errors
- Core implementation agent

### Step 6: Reviewer, Testing, Debug, Documentation Agents
- Create agent files for each
- Wire into the pipeline

### Step 7: Agent Orchestrator
- Create `backend/agents/orchestrator.py` (rewrite existing stub)
- `AgentOrchestrator.run_full_pipeline(request) → AgentContext`
- Manages agent sequencing, error recovery, state persistence

### Step 8: API v5 Router
- Create `backend/api/v5/router.py`
- Expose agent run/trace/status endpoints
- Register in `backend/main.py`

### Step 9: Tests
- Create `backend/tests/unit/test_agents_base.py`
- Create `backend/tests/integration/test_agents_pipeline.py`
- Follow existing test patterns (in-memory SQLite, local git repos)

---

## Key Design Decisions

1. **No direct file editing** — Every modification routes through Phase 3 tools
2. **All decisions explainable** — Every agent produces `AIReasoning` with
   alternatives, confidence, and risk assessment
3. **Full traceability** — `agent_trace_json` records every decision, tool call,
   and timing for post-mortem analysis
4. **Pipeline stages are composable** — Run `plan-only`, `code-only`, or `full`
   based on use case
5. **Error recovery** — If Coding Agent fails, Debug Agent diagnoses and
   suggests a fix; the pipeline retries before giving up
6. **No new databases** — Everything is JSON columns on `execution_plans` +
   existing Phase 2 agent_executions table
