# PLAN — Nightwatch Structured Analysis

> Status: IN PROGRESS
> Started: 2026-06-10
> Author: wind

## Summary

The `nightwatch` feature fetches raw data from ntopng and CrowdSec APIs and
builds a daily digest for Telegram. The raw fetchers are working, but the
previous implementation had a structural flaw: all analysis was outsourced to the
LLM by dumping raw API JSON as text into the prompt. This has been replaced with
dedicated analyzers that produce structured findings the LLM only refines.

## What's done

| Item | Status |
|------|--------|
| `ntopng_analyzer.py` — bandwidth, protocol, host, flow analysis | ✅ |
| `crowdsec_analyzer.py` — ban aggregation, scenario clustering, temporal patterns | ✅ |
| `cross_reference.py` — ban IP ↔ ntopng host correlation, subnet lateral movement | ✅ |
| `analyzers/__init__.py` — public exports | ✅ |
| `digest_builder.py` — uses pre-analyzed data instead of raw API dumps | ✅ |
| `digest_orchestrator.py` — wires analyzers into pipeline | ✅ |
| `test_nightwatch_analyzers.py` — tests for all new modules | ✅ |

## What's pending

### P1: Wire analyzers into the digest pipeline

**File:** `backend/app/nightwatch/digest_orchestrator.py`

Update `run_digest()` to call the new analyzers and pass their structured results
to the LLM instead of raw API data.

Steps:

1. Import `ntopng_analyzer` and `crowdsec_analyzer` from `analyzers` package.
2. After fetching raw data in Step 2, call the analyzers.
3. Pass analyzed results (not raw API responses) to the prompt builder in Step 3.
4. Handle empty analysis results gracefully (no crash, log warning).

Acceptance:
- [ ] `run_digest()` calls `ntopng_analyze()` and `crowdsec_analyze()` on raw data
- [ ] LLM receives structured findings, not raw JSON
- [ ] All existing test paths still pass

---

### P1: Add API endpoint for analyzer results

**File:** `backend/app/routers/nightwatch.py` (new)

Expose an endpoint so the frontend can inspect what the analyzers found.

Endpoint: `GET /api/nightwatch/analyzer-results`

Response:
```json
{
  "ntopng": {
    "findings_count": 5,
    "bandwidth_findings": [...],
    "protocol_findings": [...],
    "host_findings": [...],
    "flow_findings": [...],
    "total_bytes": 5000000
  },
  "crowdsec": {
    "findings_count": 3,
    "ban_findings": [...],
    "scenario_findings": [...],
    "temporal_findings": [...],
    "total_alerts": 12,
    "active_ban_count": 5
  },
  "cross_reference": [
    {"severity": "high", "category": "subnet_lateral_movement", "summary": "..."}
  ]
}
```

Wire the router into `app/main.py` with `app.include_router(nightwatch_router)`.

Acceptance:
- [ ] Endpoint returns pre-analyzed data (no LLM call, no Telegram send)
- [ ] Returns 200 even if analyzers found zero results
- [ ] Returns 500 if analyzers crash with details

---

### P2: Update frontend to display analyzer results

**Location:** `frontend/src/components/Dashboard.tsx` (or new `NightwatchAnalyzerPanel`)

Add a panel showing the raw analyzer findings alongside the digest output.

Acceptance:
- [ ] Panel fetches from `/api/nightwatch/analyzer-results`
- [ ] Displays findings grouped by source (ntopng, crowdsec, cross-reference)
- [ ] Color-codes by severity (critical = red, high = amber, medium = yellow, low = blue)

---

### P1: Run lints, tests, coverage gate

**Commands:**
```bash
# Backend lint
ruff check backend/app/nightwatch/ backend/tests/test_nightwatch_analyzers.py
ruff format backend/app/nightwatch/ backend/tests/test_nightwatch_analyzers.py

# Backend tests
cd backend && pytest tests/test_nightwatch_analyzers.py -v --cov=app.nightwatch.analyzers --cov-fail-under=70

# Full backend lint + test gate
pytest --cov=app --cov-fail-under=80
ruff check .
ruff format --check .
```

Acceptance:
- [ ] All analyzer tests pass
- [ ] Coverage for `nightwatch.analyzers` >= 70%
- [ ] No new lint errors beyond pre-existing ones
- [ ] Full `ruff check .` passes

---

### P2: Wire scheduled digest to use analyzers

**File:** `backend/app/scheduler.py` (or wherever the cron digest job lives)

Ensure the scheduled daily digest (not just the preview endpoint) uses the new
analyzers pipeline.

Acceptance:
- [ ] Scheduled job calls `run_digest()` which uses the analyzer pipeline
- [ ] Logs show analyzer names in output (debug level)

---

## File manifest

### New files
- `backend/app/nightwatch/analyzers/__init__.py`
- `backend/app/nightwatch/analyzers/ntopng_analyzer.py`
- `backend/app/nightwatch/analyzers/crowdsec_analyzer.py`
- `backend/app/nightwatch/analyzers/cross_reference.py`
- `backend/tests/test_nightwatch_analyzers.py`

### Modified files
- `backend/app/nightwatch/digest_builder.py` — uses pre-analyzed data
- `backend/app/nightwatch/digest_orchestrator.py` — wires analyzers in
- `frontend/src/` — analyzer results panel (pending)
- `backend/app/routers/nightwatch.py` — analyzer results endpoint (pending)
