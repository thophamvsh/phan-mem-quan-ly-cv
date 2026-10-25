# Rain forecast: implementation and operations

The feature is OFF by default. No production configuration or remote service is changed by deploying the code alone.

## Contract

`GET /api/v1/thongsothuyvan/rain-forecast/?plant=songhinh|vinhson`

- Existing authenticated user; requires realtime hydrology permission and plant scope.
- Invalid/missing plant: 400; unauthenticated: 401/403 per configured authenticator; unauthorized plant: 403.
- Disabled: 200 `{enabled:false, plant, timezone, provider, attribution_url, locations:[]}`.
- Enabled: each location has code, label, note, scope, status, fetched_at, nullable source_issued_at, revision_id, and exactly seven daily slots (today + six, Vietnam time).
- Each slot has date, nullable precipitation_mm, probability_max_pct, weather_code and quality_flags. Zero is a valid value; null is missing.
- Status: fresh / partial / stale / unavailable. Latest failed fetch or old receipt marks retained data stale. Coordinate changes invalidate the previous point's data.
- GET never calls upstream. Response is private/no-store, with authorization on every request.
- Full-day precipitation is not remaining rainfall after the current time. Daily maximum probability is not a confidence interval for daily rainfall.

## Storage and compatibility

Migration 0023 creates locations, immutable revision documents, fetch audit records and database leases. Seeds the four user-provided VRAIN points without overwriting an existing code. Ho B is explicitly labelled a station at Son Lang, not a verified dam coordinate.

Hourly and daily series are stored together in revision JSON rather than separate point tables in the initial plan. This reduces joins and prevents mixing forecast editions. It retains normalized hourly intervals, model/parser metadata and requested/returned coordinates. Index location + receipt supports latest/history reads. Export/analysis can unpack the arrays; do not change historical revisions in place.

The shared provider replaces the two chatbot HTTP clients. Leadership report preserves temperatures and its output field names. SH/VS report points now use the supplied station coordinates (VS report uses A, not combined A/B/C). TKT remains unchanged. Configured points read persisted forecasts when enabled; stale/unavailable data raises a safe error to existing report handling. Other coordinates keep a 15-minute cached provider path. Missing rainfall days are omitted from the water-tool mapping, never mapped to zero; existing forecast callers show '-' and skip rain-based uplift for these dates.

No source issue time is invented. first receipt is retained separately from repeated successful checks. No raw secret/request URL is persisted.

## Enable on Orange Pi after review

1. Confirm provider terms/commercial authorization and endpoint. Do not assume the existing free chatbot endpoint proves commercial permission.
2. Take a verified backup. Build app/worker/beat and apply migrations using the normal deployment workflow.
3. Add to server .env (do not commit secrets):

```dotenv
RAIN_FORECAST_ENABLED=true
OPEN_METEO_BASE_URL=https://customer-api.open-meteo.com/v1/forecast
OPEN_METEO_API_KEY=<configure privately on server>
```

The public endpoint is the default only for permitted use. Use the endpoint/key issued for the actual plan. All three services must receive the same configuration and be recreated after changes.

4. Run once from the backend directory:

```bash
sudo docker compose -f docker-compose.prod.yml exec app python manage.py refresh_rain_forecast
sudo docker compose -f docker-compose.prod.yml logs --tail=80 worker celery-beat
```

5. Confirm four successful location results, then test the authenticated API and frontend with SH-only, VS-only and all-factory accounts.
6. Beat schedules refresh at minute 15 every three hours, using the project's Celery timezone (verify it is Asia/Ho_Chi_Minh). Keep a single Beat instance.

Only GET refresh is exposed to frontend; its button checks the database, not the provider. No new public write endpoint is introduced.

## Failures, monitoring and rollback

Each location has a 5-minute database lease; transport has connect/read timeouts. Fetch failures retain the last revision and record sanitized error codes. A partial batch makes the Celery task fail visibly. At most three HTTP attempts use backoff/jitter for connection errors/429/selected 5xx; 401/403 and malformed payloads do not retry. Numeric Retry-After up to 30 seconds is honored; larger or HTTP-date values defer retries to a later run rather than retrying early. Inspect quota before manual retries. Admin exposes locations for controlled configuration and read-only fetch/revision history.

Check RainForecastFetch failures and data age as well as worker activity. Connect these checks to the existing external monitoring/Telegram setup before relying on unattended production; this code does not provision external accounts or Telegram integrations. R2 monthly history export is a follow-up operational step, not an implemented export job; existing database backup includes the new tables. Never apply a 30-day daily-backup lifecycle to the long-term training archive.

Rollback: set RAIN_FORECAST_ENABLED=false and recreate affected services. The card hides; legacy chatbot uses the shared cached provider client. Keep database tables/history; do not reverse migration to delete collected data. Existing VRAIN and reservoir snapshot tasks are independent.

## Verification commands (local)

```bash
python manage.py test thongsothuyvan.tests.test_rain_forecast
python manage.py makemigrations --check --dry-run
```

Frontend: run the tests in `src/features/dashboard/rain-forecast/`, ESLint on changed files and `npm run build`.

For real HTTP against a local synthetic fixture (no real key or database):

```text
postman simulation run postman/simulations/rain-forecast.sim.yaml --port 4910 --output ndjson
# In another terminal, from app/:
python -m thongsothuyvan.tests.forecast_http_probe
```

Mock follows Open-Meteo documented daily/hourly shapes. Reserved fixture latitudes 0/1/2/3 return HTML 500, JSON 429, 401 and a delayed response; the probe also checks a refused port. These are test scenarios, not real station coordinates. Owner mock discovery was unavailable without Postman login; nothing was published. Passing simulation proves handling, not live forecast accuracy or production access rights.

## Completion check: 2026-10-25

- Backend/chatbot: 54 tests passed across rain forecast, hydrology utilities, leadership report, report edges and leadership responses. The temporary in-memory SQLite database applied the migration chain successfully.
- Added regression coverage for lease replacement during an HTTP call, failed revision writes retaining the previous forecast, and plant filtering/realtime permission denial. A replaced lease cannot publish or release its successor's lock; stored errors remain sanitized.
- Django system check passed; makemigrations --check --dry-run reported no changes.
- Frontend: three forecast tests plus eight factory-access tests passed. Forecast tests cover rendered SH/VS row counts, disabled/unauthorized hiding, zero versus missing data, stale labels and Vietnam dates across year boundaries.
- ESLint passed on forecast files and the dashboard integration; production build passed. Existing large-chunk build warnings remain.
- Corrected TV table font sizing and added a visible keyboard focus outline to the horizontal scroll region. Automated markup tests do not establish visual correctness on physical mobile/TV displays; production account/browser checks remain part of rollout.
- App, worker and Beat all use the same server env_file; no live configuration, production migration or deployment was performed. The flag remains off by default.

Production readiness still requires authorized provider configuration, confirmation of the Ho B station's representativeness, a real-data smoke check, external alert wiring and the planned monthly R2 history export. Those external/operational steps are not claimed as completed by local tests.

## Synthetic frontend preview

Set `VITE_RAIN_FORECAST_DEMO=true` in VshProject's local `.env` and restart Vite (or rebuild the frontend for a preview deployment). Local preview is now enabled. Backend `RAIN_FORECAST_ENABLED` remains false. The card is on the aggregate realtime dashboard and respects the existing hydrology/plant UI permissions.

The preview labels the card and rows as synthetic, supplies SH and VS A/B/C fixtures including zero and missing rainfall, and disables the forecast API query and refresh button. It never writes forecasts or supplies chatbot data. It is an explicit preview mode, not an automatic fallback when live data fails. No live provider entitlement is implied. To switch to live data, set VITE_RAIN_FORECAST_DEMO=false, configure the authorized backend provider, enable backend collection and restart/rebuild the affected services.

### Draft inquiry to Open-Meteo (not sent)

Recipient: info@open-meteo.com
Subject: API licensing for an internal hydropower operations dashboard and AI chatbot

Hello Open-Meteo team,

We are developing an internal application for a hydropower company in Vietnam. It would display seven-day point precipitation forecasts for four station locations near Song Hinh and Vinh Son reservoirs, and use the same weather integration in an internal AI chatbot. The application is for company staff, without public subscriptions or advertising; it supports internal monitoring and planning.

The new dashboard is designed to fetch each of the four points once every three hours (about 32 requests/day before retries). The chatbot also supports other locations through a 15-minute cache, so its usage is additional and the total has not yet been measured. We plan to retain forecast revisions and hourly precipitation for historical comparison and possible internal inflow forecasting research, and display attribution.

Could you confirm whether this use requires a commercial subscription, which plan is appropriate, and whether the plan permits long-term internal storage and analysis of forecast revisions? Please also confirm any attribution requirements and the endpoint/API-key configuration we should use.

Thank you.

Send this draft from the company's own contact address after adding the company/contact details. No inquiry or subscription has been submitted by this task. Existing chatbot access to the public endpoint still requires the same usage assessment; the new dashboard preview does not change chatbot operation.
