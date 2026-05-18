# AGENTS.md

## Project
This project is a pilot MVP for a political campaign recommendation system
using Seoul public datasets.

## Objective
Build a minimal working prototype that recommends:
- top 3 campaign places
- recommendation reasons
- message categories

based on:
- time_slot
- target_age_group
- place_type

## Tech Stack
- Frontend: Next.js
- Backend: FastAPI
- Data Processing: Python, pandas

## Current Scope
Focus only on MVP.
Do not add unnecessary features.

## Data
Use only a few pilot datasets first:
- subway ridership
- park data
- traditional market data
- senior welfare facility data

## Constraints
- Keep implementation simple.
- Prefer readable code over over-engineering.
- Do not introduce authentication.
- Do not introduce database unless explicitly requested.
- Use CSV-based local data first.
- Keep APIs minimal.

## Coding Style
- Use clear function names.
- Use snake_case for Python.
- Keep files small and modular.

## Done Means
A task is done only if:
- code runs locally
- basic errors are handled
- output format matches the requested spec