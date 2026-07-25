# ADR 001: Unified GPS Location Tracking & Live Monitoring

**Date:** 2026-07-25

**Status:** Accepted

## Context

The fleet currently uses two separate GPS tracking providers:
- **Cartrack** — primary provider for most trucks, exposes trip/event/fuel data and a real-time position endpoint
- **TrackSolid Pro** — secondary provider for GNN403 and NKC4763, exposes raw GPS points via `jimi.device.track.list`

The Daily Log already aggregates trip data from both into a single table, but there is no unified map showing all trucks' locations. Users must visit each provider's separate portal to see where trucks are.

## Decision

We will build a unified GPS location tracking system with two modes:

### 1. Historical Track (on Daily Log)
- Raw GPS points from TrackSolid pulls are persisted in a new `VehiclePosition` model
- When viewing a single day in Daily Log, a Leaflet map shows the truck's breadcrumb trail for that date
- Data source: TrackSolid track history (already fetched), Cartrack trip start/end positions if available

### 2. Live Monitoring Dashboard (full-screen map)
- New page at `/fleetops/tracking/` with a full-window Leaflet map
- Browser polls the Django server every **5 minutes** via `/fleetops/api/positions/latest/`
- Django fetches current positions from **both** providers:
  - Cartrack: real-time position endpoint (`/position` or equivalent)
  - TrackSolid: latest known position from `VehiclePosition` table
- Returns combined JSON, displayed as color-coded markers (Cartrack=blue, TrackSolid=orange)
- No external paid service — Leaflet + OpenStreetMap tiles are free, no API key

### Data Retention
- `VehiclePosition` records are auto-purged after **90 days**
- Purge runs on import (when new data is written, old records beyond 90d are deleted)

### Technical Stack
- **Frontend:** Leaflet.js (CDN), OpenStreetMap tiles
- **Backend:** Django JSON endpoints, no new libraries needed
- **No paid services** — all data comes from existing Cartrack and TrackSolid subscriptions

### New Model: `VehiclePosition`
```
truck         → FK → Truck
provider      → CharField (CARTRACK / TRACKSOLID)
latitude      → DecimalField(9,6)
longitude     → DecimalField(9,6)
speed_kmh     → DecimalField(6,1) [nullable]
heading       → IntegerField [nullable]
recorded_at   → DateTimeField
ignition_on   → BooleanField [nullable]
extra_data    → JSONField [nullable]
created_at    → DateTimeField [auto_now_add]
Index: (truck, -recorded_at)
```

## Consequences

### Positive
- Single pane-of-glass view of all trucks regardless of provider
- No extra cost — Leaflet is free, all data from existing APIs
- Historical GPS trail available for trip review
- 90-day retention balances usefulness with storage cost

### Negative
- 5-minute refresh is not true real-time — sufficient for fleet monitoring but not for dispatch
- Cartrack real-time endpoint needs to be discovered and integrated (may need testing)
- `VehiclePosition` table grows by ~500-2000 rows/day (manageable with 90d purge)

### Risks
- Cartrack may not expose a suitable position endpoint — fallback: rely solely on TrackSolid for live data
- TrackSolid token may expire mid-session — handled by `_get_token()` caching
- 5-min polling does not impact Render free tier (one small request per 5 minutes)

## Implementation Order
1. Create `VehiclePosition` model + migration
2. Add Cartrack `get_positions()` method
3. Bulk-create `VehiclePosition` from TrackSolid GPS points in import
4. Build JSON API endpoints (`latest`, `history`)
5. Build Live Tracking template with Leaflet
6. Add historical map to Daily Log
7. Add sidebar nav item
8. Tests
