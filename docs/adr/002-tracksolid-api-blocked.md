# ADR 002: TrackSolid Open API Blocked by Server-Side NullPointerException

**Date:** 2026-07-25

**Status:** Accepted (blocked — awaiting vendor fix)

## Context

TrackSolid Pro is the secondary GPS provider for trucks GNN403 (IMEI `869066063765607`) and NKC4763 (IMEI `869247060084669`). The Open API at `hk-open.tracksolidpro.com` is required to:

1. Obtain an access token (`jimi.oauth.token.get`)
2. List devices (`jimi.user.device.list`)
3. Get device details (`jimi.track.device.detail`)
4. Pull GPS track history (`jimi.device.track.list`)

All subsequent calls depend on step 1 (access token), which is currently unobtainable.

## Investigation

### What was tried

| Approach | Result |
|---|---|
| POST `/route/rest` with `json=params` | `code=1001` method name missing — router expects form-urlencoded |
| POST `/route/rest` with `data=params` (form-urlencoded) | `500 NullPointerException` at `/v1/oauth/getAccessToken` |
| GET/POST `/v1/oauth/getAccessToken` (direct REST) | `500 NullPointerException` — same crash |
| GET `/route/rest` with query params | `500 NullPointerException` after param validation passes |
| JSON Content-Type (explicit) | `500 NullPointerException` |
| GET with query string (minimal params) | `500 NullPointerException` |
| Wrong sign / wrong user_id / wrong app_key | `500 NullPointerException` — crash before credential check |

### What works

The `/route/rest` validation layer correctly returns `code=1001` errors for:
- Missing `sign_method` → "Missing signature method parameter or illegal signature method"
- Missing/wrong `method` → "A method name parameter is missing or a method name does not exist"
- Wrong timestamp format → "Missing timestamp parameter or illegal timestamp"
- Missing `format` → "Missing data format parameter or data format error"

This confirms our parameter naming, types, and format are correct.

### Root cause

The Spring Boot controller at `/v1/oauth/getAccessToken` has a `java.lang.NullPointerException` in its method body. The `@RequestParam` validation succeeds, the method is dispatched correctly, but the implementation crashes — likely on a null service bean, null database lookup result, or null configuration value. This is a **server-side bug** that cannot be worked around from our client.

## Decision

1. The `TracksolidClient` implementation in `tracksolid_import.py` uses the correct API protocol (POST `/route/rest`, form-urlencoded, `method` + `sign_method=md5` + `sign` + snake_case params). No further client-side changes needed.
2. The NPE is detected explicitly and surfaced to the user with a clear message directing them to contact TrackSolid support.
3. TrackSolid support has been contacted with full request/response details, account credentials, and debugging evidence.
4. The TrackSolid import feature is disabled (by the NPE) until the vendor fixes their endpoint.

## Consequences

### Positive
- Cartrack import is completely unaffected — separate client class, shared only at the view level
- All 43 fleetops tests pass
- When TrackSolid fixes the NPE, `TracksolidClient` can obtain a token immediately — no client changes expected
- The `import_tracksolid_data` function, `_process_track`, Haversine distance, and all utility code are fully tested and ready

### Negative
- TrackSolid data cannot be pulled into Daily Log until the vendor resolves the NPE
- GPS tracking ADR (ADR 001) step 3 (bulk-create VehiclePosition from TrackSolid) is blocked
- No live tracking for GNN403 and NKC4763 until the token endpoint works
- The user experience is: checking the TrackSolid checkbox and clicking Pull Cartrack yields an error message

### Risks
- TrackSolid may take days or weeks to respond/fix
- If they change their API during the fix, client adjustments may be needed
- No fallback provider for GNN403 and NKC4763 — these trucks will lack GPS data until resolved

## Next Steps (when NPE is fixed)
1. Update `TRACKSOLID_API_URL` if the endpoint changes
2. Obtain token → list devices → confirm GNN403 and NKC4763 appear
3. Pull track history for both IMEIs → process via `_process_track` → create/update `DailyLog`
4. Proceed with GPS tracking ADR implementation (VehiclePosition model, Leaflet map)
