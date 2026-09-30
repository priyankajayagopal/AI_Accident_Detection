# API (FastAPI, http://localhost:8000/docs for Swagger)
| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | status + orchestrator engine |
| GET | /api/incidents, /api/incidents/{id} | list / detail (+events + agent trace) |
| POST | /api/incidents/proposals | external pipeline posts a candidate |
| POST | /api/incidents/{id}/approve \| reject \| close | HUMAN gate `{operator}` (403 if unknown, 409 if illegal) |
| GET | /api/incidents/{id}/report, /evidence/{file} | report markdown, keyframes/clip/plot |
| GET | /api/cameras; POST /api/cameras/{id}/start, /stop; GET /api/cameras/{id}/stream | camera grid, MJPEG live video |
| GET | /api/alerts, /api/escalations, /api/audit/verify, /api/map, /api/metrics/summary | alerts, escalations, audit integrity, map graph |
| WS | /ws | live events: incident_created/updated, agent_step, alert, traffic, camera |
