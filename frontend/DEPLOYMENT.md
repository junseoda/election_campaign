# Vercel Deployment Guide

## Project Overview

This frontend is a Next.js App Router web app for a campaign route and venue recommendation system based on Seoul public data and candidate schedule evaluation results.

The recommendation, route, and evaluation screens call the existing FastAPI backend through `NEXT_PUBLIC_API_BASE_URL`. The backend reads the CSV outputs under the project-level `output/` directory. Do not regenerate, overwrite, or delete those CSV files during frontend deployment work.

## Local Run

From the Vercel root directory:

```bash
cd frontend
npm install
npm run build
npm run dev
```

The local frontend defaults to `http://127.0.0.1:3000`. For full data loading, run the backend separately at `http://127.0.0.1:8000` or set `NEXT_PUBLIC_API_BASE_URL` to another backend URL.

## Environment Variables

Create `frontend/.env.local` for local values. This file is ignored by git.

```bash
NEXT_PUBLIC_KAKAO_MAP_API_KEY=
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_APP_NAME=Campaign Recommender
```

`NEXT_PUBLIC_KAKAO_MAP_API_KEY` is exposed to the browser because the Kakao Maps JavaScript SDK requires a client-side app key. Do not put server secrets in any `NEXT_PUBLIC_` variable.

The map component also accepts the previous local variable name, `NEXT_PUBLIC_KAKAO_MAP_JS_KEY`, for backward compatibility. New Vercel deployments should use `NEXT_PUBLIC_KAKAO_MAP_API_KEY`.

## Vercel Deployment Settings

- Framework Preset: `Next.js`
- Root Directory: `frontend`
- Install Command: `npm install`
- Build Command: `npm run build`
- Output Directory: leave empty

No `vercel.json` is required for the current Next.js project.

## Vercel Environment Variables

Set these in Vercel Project Settings -> Environment Variables:

```bash
NEXT_PUBLIC_KAKAO_MAP_API_KEY=
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_APP_NAME=Campaign Recommender
```

For `NEXT_PUBLIC_API_BASE_URL`, use the public URL of the deployed backend API if the recommendation/evaluation data should load in production. If this variable is omitted, the app falls back to the local backend URL and pages will show a friendly loading error instead of crashing.

## Main Routes

- `/`
- `/recommend`
- `/route`
- `/evaluation`
- `/map`
- `/demo`

The required deployment-check routes are `/`, `/recommend`, `/route`, and `/evaluation`.

## Data File Notes

The frontend does not directly copy or rewrite CSV files. The existing backend reads the project-level CSV outputs, including:

- `output/recommendation_results.csv`
- `output/evaluation_result_summary.csv`
- `output/raw_baseline_recommendations.csv`
- `output/experiments/**`

Keep `data/` and `output/` tracked if they are needed by the backend or experiment reproduction workflow. Do not add broad ignore rules for these directories.

## Pre-Deploy Checks

Run these before deploying:

```bash
npm install
npm run build
npm run dev
```

Then verify that `/`, `/recommend`, `/route`, and `/evaluation` open without a fatal error. If the backend is unavailable, the pages should render an error fallback rather than crashing.
