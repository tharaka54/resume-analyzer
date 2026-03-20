# 🎯 ResumeAI — AI-Powered Resume Analyzer & Ranking System

> An intelligent recruiter tool that scores, ranks, and explains candidate resumes using a hybrid TF-IDF + BERT model with Claude AI explanations.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [AI Scoring Pipeline](#ai-scoring-pipeline)
4. [Quick Start (Docker)](#quick-start-docker)
5. [Local Development](#local-development)
6. [API Reference](#api-reference)
7. [Environment Variables](#environment-variables)
8. [Security Model](#security-model)
9. [Functional Requirements](#functional-requirements)
10. [Troubleshooting](#troubleshooting)

---

## Overview

ResumeAI lets recruiters:
1. **Create job postings** with full descriptions
2. **Upload candidate PDFs** through a 4-layer security pipeline
3. **Run AI ranking** in real-time via WebSocket with live progress
4. **View scores** across Bar and Radar charts (Chart.js)
5. **Read plain-English AI explanations** powered by Claude API
6. **Export rankings** to CSV in one click

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0, PyMongo, flask-sock |
| Auth | Google OAuth 2.0, JWT (HS256) |
| AI/NLP | TF-IDF (scikit-learn), BERT (sentence-transformers), spaCy, Claude API |
| Database | MongoDB 7.0 |
| Frontend | React 18, React Router, Chart.js, Vite |
| Security | PyMuPDF, 4-layer PDF validation |
| Deploy | Docker Compose (single command) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend (Vite)                 │
│  Login → Dashboard → Upload → LiveRanking → Charts → View   │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                     Flask API (Python 3.11)                  │
│                                                              │
│  /auth/*   Google OAuth 2.0 + JWT tokens                    │
│  /jobs/*   CRUD job postings                                 │
│  /resumes/* PDF upload (4-layer security) + text extract    │
│  /ranking/* AI scoring + CSV export                         │
│  /ws/ranking/<job_id>   WebSocket live progress              │
└──────────┬──────────────────────┬──────────────────────────┘
           │                      │
    ┌──────▼──────┐     ┌────────▼────────┐
    │  MongoDB 7  │     │   AI Engine      │
    │  users      │     │  TF-IDF (40%)   │
    │  jobs       │     │  BERT (60%)     │
    │  resumes    │     │  spaCy skills   │
    └─────────────┘     │  Claude API     │
                        └─────────────────┘
```

---

## AI Scoring Pipeline

```
PDF Upload
    ↓
[4-Layer Security] — extension → magic bytes → PyMuPDF scan → UUID rename
    ↓
[preprocess.py] — lowercase, stopwords, lemmatize, noise removal
    ↓
    ├── [tfidf_model.py]     → Keyword score  (exact matches, bigrams)
    ├── [bert_model.py]      → Semantic score (sentence-transformers)
    └── [skill_extractor.py] → Skill gap list (spaCy + regex)
              ↓
    [hybrid_scorer.py]  →  Final = TF-IDF×0.4 + BERT×0.6
              ↓
    [llm_explainer.py]  →  Claude claude-3-5-sonnet-20241022 explanation
              ↓
    WebSocket → React dashboard → Charts + AI Card + Skill Pills + CSV
```

### Why 40/60 Split?
- **TF-IDF (40%)** ensures specific required technologies (React, MongoDB) are present keyword-for-keyword
- **BERT (60%)** understands role alignment and catches paraphrased experience
- Combined, they outperform either model alone (see `notebooks/04_model_comparison.ipynb`)

---

## Quick Start (Docker)

### Prerequisites
- Docker Desktop installed and running
- Google OAuth credentials (from Google Cloud Console)
- Anthropic API key (from console.anthropic.com) — *optional, fallback explanation used if absent*

### 1. Configure environment
```bash
cp .env .env.local
# Edit .env with your actual credentials:
nano .env
```

Required values:
```env
GOOGLE_CLIENT_ID=your-actual-google-client-id
GOOGLE_CLIENT_SECRET=your-actual-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
ANTHROPIC_API_KEY=sk-ant-...   # Optional
FLASK_SECRET_KEY=change-this-random-string-32-chars
JWT_SECRET_KEY=another-random-32-char-string
```

### 2. Start everything
```bash
docker-compose up --build
```

Wait ~2-3 minutes for models to download (BERT: ~80 MB, spaCy: ~40 MB).

### 3. Access the app
| Service | URL |
|---------|-----|
| React Frontend | http://localhost:3000 |
| Flask API | http://localhost:5000 |
| Health Check | http://localhost:5000/health |
| MongoDB | localhost:27017 |

---

## Local Development

### Backend (Flask)
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Download NLP models
python -m spacy download en_core_web_md

# Start backend
python run.py
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

The Vite dev server proxies all `/auth`, `/jobs`, `/resumes`, `/ranking` requests to `http://localhost:5000`.

---

## API Reference

### Auth
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Redirect to Google OAuth |
| GET | `/auth/callback` | OAuth callback — returns JWT via redirect |
| POST | `/auth/refresh` | Exchange refresh token for new access token |
| GET | `/auth/me` | Get current user info |

### Jobs
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/jobs/` | ✅ | Create job posting |
| GET | `/jobs/` | ✅ | List all jobs |
| GET | `/jobs/<id>` | ✅ | Get single job |
| PUT | `/jobs/<id>` | ✅ | Update job |
| DELETE | `/jobs/<id>` | ✅ | Delete job + resumes |

### Resumes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/resumes/<job_id>/upload` | ✅ | Upload PDF (multipart/form-data) |
| GET | `/resumes/<job_id>` | ✅ | List resumes for job |
| GET | `/resumes/detail/<resume_id>` | ✅ | Full resume with raw text |
| DELETE | `/resumes/detail/<resume_id>` | ✅ | Delete resume |

### Ranking
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ranking/<job_id>` | ✅ | Run full AI ranking |
| GET | `/ranking/<job_id>/results` | ✅ | Get cached results |
| GET | `/ranking/<job_id>/export/csv` | ✅ | Download CSV |

### WebSocket
| Path | Description |
|------|-------------|
| `ws://localhost:5000/ws/ranking/<job_id>?token=<jwt>` | Live ranking feed |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | ✅ | Flask session signing key |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | ✅ | Must match Google Console |
| `JWT_SECRET_KEY` | ✅ | JWT signing secret |
| `ANTHROPIC_API_KEY` | ⚠️ | Claude API (fallback if absent) |
| `JWT_ACCESS_EXPIRES_MINUTES` | ❌ | Default: 60 |
| `JWT_REFRESH_EXPIRES_DAYS` | ❌ | Default: 30 |
| `MAX_CONTENT_LENGTH` | ❌ | Default: 5242880 (5 MB) |

---

## Security Model

### PDF Upload — 4 Layers

| Layer | Module | What It Checks |
|-------|--------|----------------|
| 1 | `file_validator.py` | Extension `.pdf`, MIME `application/pdf`, size ≤ 5 MB |
| 2a | `magic_bytes.py` | Binary header `%PDF-` (catches renamed executables) |
| 2b | `pdf_inspector.py` | PyMuPDF deep scan — blocks JS, launch actions, embedded executables |
| 3 | `filename_sanitizer.py` | Discards original filename, assigns UUID4 (prevents path traversal) |

### Auth Security
- Google OAuth 2.0 with CSRF state token verification
- JWT signed with HS256, short-lived access tokens (60 min)
- Long-lived refresh tokens (30 days) for seamless re-auth

---

## Functional Requirements Coverage

| ID | Requirement | Status |
|----|-------------|--------|
| F1 | Google OAuth login | ✅ `/auth/login` + `/auth/callback` |
| F2 | Job CRUD | ✅ `/jobs/*` endpoints |
| F3 | PDF upload with 4-layer security | ✅ `app/security/` |
| F4 | Text extraction from PDF | ✅ PyMuPDF in `pdf_inspector.py` |
| F5 | TF-IDF keyword score | ✅ `tfidf_model.py` |
| F6 | BERT semantic score | ✅ `bert_model.py` |
| F7 | Hybrid final score | ✅ `hybrid_scorer.py` (40/60) |
| F8 | Matched/missing skills | ✅ `skill_extractor.py` |
| F9 | Claude AI explanation | ✅ `llm_explainer.py` |
| F10 | Live WebSocket ranking | ✅ `ws_ranking.py` + `LiveRanking.jsx` |
| F11 | Charts (bar + radar) | ✅ `RankingChart.jsx` + Chart.js |
| F12 | CSV export | ✅ `/ranking/<id>/export/csv` |
| F13 | Skill highlighting in CV view | ✅ `ResumeView.jsx` (innerHTML highlight) |

---

## Troubleshooting

### `docker-compose up` fails with MongoDB connection error
MongoDB may still be starting. Wait for the health check or run:
```bash
docker-compose restart api
```

### BERT model download is slow
The first run downloads `all-MiniLM-L6-v2` (~80 MB). Subsequent starts use the cached model. Set `TRANSFORMERS_CACHE` in `.env` to a persistent volume.

### Google OAuth `redirect_uri_mismatch`
The `GOOGLE_REDIRECT_URI` in `.env` must exactly match what's registered in Google Cloud Console → OAuth 2.0 credentials → Authorized redirect URIs.

### `spacy.errors.E050` — Model not found
```bash
python -m spacy download en_core_web_md
# or the smaller model:
python -m spacy download en_core_web_sm
```

### WebSocket connection refused
Ensure `flask-sock` is installed and `FLASK_DEBUG=True` is NOT set in production (use gunicorn with gevent worker instead).

### Claude API returns empty explanation
Check `ANTHROPIC_API_KEY` is set correctly. The system uses a rule-based fallback explanation automatically if the API is unavailable.

---

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `01_tfidf_baseline.ipynb` | TF-IDF experiments, n-gram comparison |
| `02_bert_semantic.ipynb` | BERT similarity heatmaps, CPU benchmarks |
| `03_skill_extraction.ipynb` | spaCy skill gap visualisation |
| `04_model_comparison.ipynb` | TF-IDF vs BERT vs Hybrid comparison |
| `05_final_model.ipynb` | Final model validation and radar chart |

Run with: `cd resume-analyzer && jupyter lab notebooks/`

---

## License

CSG3101 Applied Project — Academic Use Only
