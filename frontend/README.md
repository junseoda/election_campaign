# Frontend Demo

## Run

1. `cd frontend`
2. `npm install`
3. `npm run dev`

The app uses Next.js API routes by default, so `/recommend`, `/route`, and `/evaluation` work from bundled local JSON/CSV data without a separate backend.

Optional FastAPI integration can be enabled with `API_BASE_URL` in `.env.local`; do not set a localhost URL in production.
