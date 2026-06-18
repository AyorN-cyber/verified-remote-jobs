# Web App Plan

The CLI is useful for development, but a user-facing product should be a web app.

## Recommended MVP

Build a web app with:

- CV upload or pasted profile
- target role selection
- target country/global eligibility settings
- freshness window setting
- API key settings or hosted credits
- scan progress screen
- approved/manual/rejected tabs
- evidence panel per job
- DOCX/CSV/XLSX export
- saved runs

## Suggested Stack

- Frontend: Next.js or React
- Backend: FastAPI
- Queue: Celery/RQ or a hosted background-job system
- Database: PostgreSQL
- Storage: local/S3-compatible object storage for generated exports
- Auth: Clerk, Auth.js, Supabase Auth, or similar
- Billing later: Stripe

## Product Positioning

Lead with anti-scam and eligibility verification:

> Find remote jobs you can actually apply for. Verify freshness, country eligibility, company source, and application links before wasting time.

Avoid promising guaranteed employment. The product should promise better filtering and evidence, not job outcomes.

## X Launch Notes

Use X for organic posts first, then paid ads only after the landing page and privacy policy are ready. Do not automate DMs or spam recruiters. Keep posts transparent and link to a landing page with examples, pricing/waitlist, and a clear disclaimer.
