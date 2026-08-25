# Heat Wave Early Warning System — Project & Agent Build Guide

> **Notice for Collaborators and AI Agents**: 
> This document (`BUILD.md`) serves as the single source of truth for project architecture, environment setup, active configuration, coding conventions, and task completion state. 
> Whenever an AI agent or team member works on a task, read this document first to avoid code, schema, or environment mismatches. **Always update this file upon completing each task.**

---

## 1. Project Overview
- **Project Name**: SIH Heat Wave Early Warning System
- **Repository Root**: `SIH-Heat_Wave_Early_Warning`
- **Current Stack**:
  - **Backend**: FastAPI, Uvicorn, Python 3.11+
  - **Environment**: Virtual Environment (`.venv`)

---

## 2. Directory Structure & Architecture

```text
SIH-Heat_Wave_Early_Warning/
├── .gitignore               # Standard Python & environment gitignore
├── BUILD.md                 # Agent & Developer build guide (this file)
├── README.md                # General project overview
└── backend/
    ├── requirements.txt     # Python dependencies
    └── app/
        ├── __init__.py      # Package marker
        └── main.py          # FastAPI app entry point & route definitions
```

### Module Layout Conventions (For Future Tasks)
When extending the backend in upcoming tasks, adhere strictly to the following directory layout inside `backend/app/`:
- `backend/app/api/` or `backend/app/routers/` &rarr; API route controllers (e.g. `alerts.py`, `predictions.py`, `auth.py`).
- `backend/app/core/` &rarr; Application configuration, settings (`config.py`), security.
- `backend/app/models/` &rarr; Database / ORM models (e.g. SQLAlchemy, SQLModel).
- `backend/app/schemas/` &rarr; Pydantic request/response validation schemas.
- `backend/app/services/` &rarr; Business logic, ML model inference, external weather API integrations.
- `backend/app/utils/` &rarr; Helper functions and utilities.

---

## 3. Environment & Setup Instructions

### Python Version
- **Recommended**: Python `3.10` or `3.11`

### Local Setup (Backend)

1. **Navigate to the `backend` folder**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD)**:
     ```cmd
     python -m venv .venv
     .\.venv\Scripts\activate.bat
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Development Server**:
   ```bash
   uvicorn app.main:app --reload
   ```
   *Server will run at `http://127.0.0.1:8000` with hot reloading enabled.*

---

## 4. Environment Variables Specification

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| *(None currently)* | No | — | Task 1 requires no environment variables. Future variables will be listed here. |

> **Rule for AI Agents**: If adding environment variables in future tasks:
> 1. Use `pydantic-settings` or `python-dotenv`.
> 2. Document every new variable in this table.
> 3. Provide a `backend/.env.example` template with dummy values. Never commit actual `.env` files.

---

## 5. Active Endpoints & Health Check

| Method | Endpoint | Description | Expected Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Application health check | `{"status": "ok"}` |
| `GET` | `/docs` | Interactive Swagger API Docs | OpenAPI UI |
| `GET` | `/redoc` | Alternative ReDoc documentation | ReDoc UI |

---

## 6. AI Agent Collaboration Rules & Guidelines

To ensure seamless multi-agent and multi-developer collaboration without merge conflicts or code regressions:

1. **Strict Scoping**: Stick strictly to the assigned task without removing or rewriting existing valid modules unless explicitly instructed.
2. **Dependency Management**: If a new library is required, pin the minimum version in `backend/requirements.txt` (e.g. `package>=x.y.z`).
3. **Pydantic Validation**: All request payloads and response bodies for new endpoints must use Pydantic `BaseModel` schemas.
4. **Error Handling**: Use standard FastAPI `HTTPException` with clear status codes and error detail messages.
5. **Update BUILD.md**: Every AI agent **MUST** update this `BUILD.md` file at the end of each task to record new endpoints, architecture updates, new dependencies, or newly introduced environment variables.

---

## 7. Task Changelog & Status

- **Task 1: Scaffolding & Health Check** *(Completed)*
  - Initialized `backend/app/` package structure.
  - Created `backend/app/main.py` with FastAPI instance and `GET /health` endpoint.
  - Created `backend/requirements.txt` (`fastapi`, `uvicorn`).
  - Added `.gitignore` and `BUILD.md`.
