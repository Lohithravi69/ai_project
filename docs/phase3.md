# Phase 3 Foundation

Phase 3 begins the transition from AI assistant behavior to AI software engineer behavior.

## Rules

- Every modifying action must be planned before execution.
- Every modifying action must support a dry run.
- Every modifying action must create a checkpoint before it writes.
- Every tool invocation must be logged.
- Direct arbitrary Python execution is not allowed.
- Rollback must be a single API call.

## Tool Registry

The first registered tools are:

- ReadFile
- WriteFile
- SearchRepository
- ListFiles
- GitStatus
- GitDiff
- CreateBranch
- CommitChanges
- RollbackCommit
- ExecuteTests
- ExecuteShell
- QueryVectorStore
- QueryPostgres

Tool metadata includes:

- name
- description
- input schema
- output schema
- permission level
- timeout
- rollback support
- dry-run support

## Workflow

1. Generate a plan.
2. Generate a dry-run preview.
3. Show the diff and explanation.
4. Wait for approval.
5. Execute the approved tool.
6. Validate the result.
7. Commit the change if applicable.
8. Create a checkpoint.

## API

- `GET /api/v3/tools`
- `POST /api/v3/plans`
- `GET /api/v3/plans/{plan_id}`
- `POST /api/v3/plans/{plan_id}/approve`
- `POST /api/v3/tools/invoke`
- `GET /api/v3/checkpoints`
- `POST /api/v3/checkpoints/{checkpoint_id}/rollback`

## Notes

This slice intentionally keeps autonomous multi-agent workflows, self-healing loops, and automatic code merging out of scope.
