# Vercel Deployment Guide

## Project Overview

This frontend is a Next.js App Router web app for a campaign route and venue recommendation system based on Seoul public data and candidate schedule evaluation results.

The recommendation, route, and evaluation screens call Next.js API routes first. Those route handlers can call a FastAPI backend through `API_BASE_URL` when one is configured, then automatically fall back to bundled local JSON/CSV data.

## Local Run

From the Vercel root directory:

```bash
cd frontend
npm install
npm run build
npm run dev
```

The local frontend defaults to `http://127.0.0.1:3000`. A separate backend is optional; the app renders from local project data when `API_BASE_URL` is empty.

## Environment Variables

Create `frontend/.env.local` for local values. This file is ignored by git.

```bash
NEXT_PUBLIC_KAKAO_MAP_API_KEY=
NEXT_PUBLIC_API_BASE_URL=
API_BASE_URL=
NEXT_PUBLIC_APP_ENV=local
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
API_BASE_URL=
NEXT_PUBLIC_APP_ENV=production
NEXT_PUBLIC_APP_NAME=Campaign Recommender
```

Leave `NEXT_PUBLIC_API_BASE_URL` empty unless the browser truly needs a public API URL. Use server-only `API_BASE_URL` for an optional deployed FastAPI backend. If both are omitted, the app uses local JSON/CSV data through Next.js API routes and does not call localhost in production.

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
npm run qa
```

Then verify that `/`, `/recommend`, `/route`, `/evaluation`, `/api/health`, `/api/recommend`, `/api/route`, and `/api/evaluation/summary` respond normally.
