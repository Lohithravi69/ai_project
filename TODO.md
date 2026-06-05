# Phase 1 - TODO

- [x] Implement Celery scan task to actually run repository scanning and update DB/vector memory.
- [x] Fix FastAPI `/repositories/{repository_id}/sync` endpoint parameter parsing for `token`.
- [x] Prevent event-loop blocking by wrapping Git operations in `asyncio.to_thread`.
- [ ] Run quick sanity checks (lint/import check + import app).
 - [x] Run quick sanity checks (lint/import check + import app).


