# 🎯 HireIQ — AI-Powered Resume Analyzer & Ranking System
<br/>
<img src="app/static/img/logo.png" alt="HireIQ Logo" width="150" style="border-radius: 10px;" />

> An intelligent end-to-end recruitment platform that scores, ranks, and explains candidate resumes using a multi-signal AI pipeline — combining TF-IDF keyword matching, BERT semantic similarity, an AI-generated quiz, and a Random Forest hiring predictor, with plain-English explanations powered by Google Gemini.
>
> **Zero build step.** The frontend is a **vanilla HTML + JavaScript SPA** served directly by Flask — no React, no npm, no bundler required.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [AI Scoring Pipeline](#ai-scoring-pipeline)
4. [Quiz System](#quiz-system)
5. [Candidate Application Tracking](#candidate-application-tracking)
6. [Quick Start (Docker)](#quick-start-docker)
7. [Local Development](#local-development)
8. [API Reference](#api-reference)
9. [Environment Variables](#environment-variables)
10. [Security Model](#security-model)
11. [Functional Requirements](#functional-requirements)
12. [Notebooks](#notebooks)
13. [Troubleshooting](#troubleshooting)

---

## Overview

HireIQ is a full-stack recruitment tool with **two user roles**:

### 🏢 For Recruiters
1. **Create job postings** with a full description
2. **Upload candidate PDFs** through a consolidated 4-layer security pipeline
3. **Generate AI quizzes** automatically from the job description via Gemini
4. **Run AI ranking** in real-time via WebSocket with live per-resume progress
5. **View multi-dimensional scores** including hybrid, quiz, TF-IDF, and BERT scores
6. **Read plain-English AI explanations** powered by Google Gemini 2.5 Flash
7. **Update candidate status** (Under Review → Shortlisted → Selected → Rejected)
8. **Export rankings** to CSV in one click

### 👤 For Candidates
1. **Browse open job listings** without authentication
2. **Upload their own resume** to apply for a role
3. **Take the AI-generated quiz** (up to 2 attempts, 24 h cooldown, 10 min timer)
4. **View their application status** through a personal dashboard

---

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0, PyMongo, flask-sock |
| Auth | Google OAuth 2.0, JWT (HS256) |
| AI/NLP | TF-IDF (scikit-learn), BERT (sentence-transformers), spaCy, Google Gemini 2.5 Flash |
| ML | Random Forest (scikit-learn, pre-trained `random_forest_v1.pkl`) |
| Database | MongoDB 7.0 |
| Frontend | Vanilla HTML5, Vanilla CSS, Vanilla JavaScript (History API SPA) |
| Templating | Jinja2 — Flask serves `app/templates/index.html`; JS in `app/static/js/app.js` |
| Security | PyMuPDF, consolidated 4-layer PDF validation (`upload_security.py`) |
| Deploy | Docker Compose (single command) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│            Vanilla HTML/JS SPA  (Flask serves index.html)            │
│  app/templates/index.html  +  app/static/js/app.js (748 lines)      │
│                                                                      │
│  Routes (client-side, History API):                                  │
│   /                 → Public job listings                            │
│   /job/<id>         → Job details + Apply button                     │
│   /quiz/<id>        → AI pre-screening quiz (10 min timer)           │
│   /upload-cv/<id>   → PDF upload form                               │
│   /dashboard        → Recruiter job management                       │
│   /job-applicants/<id> → Ranked applicants + status controls        │
│   /resume-view/<id> → Highlighted CV viewer + score panel           │
│   /my-applications  → Candidate application status tracker          │
│   /post-job         → Create job + trigger quiz generation          │
│   /edit-job/<id>    → Edit existing job posting                     │
└───────────────────────────┬─────────────────────────────────────────┘
                             │ REST + WebSocket (JWT)
┌───────────────────────────▼─────────────────────────────────────────┐
│                     Flask API  (Python 3.11)                         │
│                                                                      │
│  /auth/*    Google OAuth 2.0 + JWT tokens                           │
│  /jobs/*    CRUD job postings                                        │
│  /resumes/* PDF upload (4-layer security) + tracking + my-apps      │
│  /ranking/* AI scoring + CSV export                                 │
│  /quiz/*    AI quiz generation, session, grading                    │
│  /ws/ranking/<job_id>   WebSocket live progress                     │
└──────────┬──────────────────────────────────┬───────────────────────┘
           │                                  │
    ┌──────▼──────┐                  ┌────────▼──────────────────────┐
    │  MongoDB 7  │                  │         AI Engine              │
    │  users      │                  │  TF-IDF    (32% of score)     │
    │  jobs       │                  │  BERT      (48% of score)     │
    │  resumes    │                  │  Quiz      (20% of score)     │
    │  quiz_pool  │                  │  spaCy skills extraction      │
    │  quiz_sessions│                │  Random Forest hiring pred.   │
    │  quiz_attempts│                │  Gemini 2.5 Flash explanation │
    └─────────────┘                  └───────────────────────────────┘
```

---

## AI Scoring Pipeline

```
PDF Upload (candidate)
    ↓
[4-Layer Security — upload_security.py]
  Layer 1  →  Extension (.pdf), MIME, size ≤ 5 MB
  Layer 2a →  Magic bytes  (%PDF- binary header)
  Layer 2b →  PyMuPDF deep scan  (JS, launch actions, embedded execs)
  Layer 3  →  UUID4 rename  (path traversal guard)
    ↓
[preprocess.py]  →  lowercase, stopwords, lemmatize, noise removal
    ↓
    ├── [tfidf_model.py]      → Keyword score        (exact + bigram)
    ├── [bert_model.py]       → Semantic score        (sentence-transformers)
    └── [skill_extractor.py]  → Skill gap list        (spaCy + regex)
              ↓
    [quiz score]              → Candidate's best quiz attempt / 10
              ↓
    [hybrid_scorer.py]  →  Final = TF-IDF×0.32 + BERT×0.48 + Quiz×0.20
              ↓
    [rf_predictor.py]   →  Random Forest  →  HIRED / REJECTED + probability
              ↓
    [llm_explainer.py]  →  Google Gemini 2.5 Flash explanation (2–3 paragraphs)
              ↓
    WebSocket → browser (native WebSocket API) → live progress bar + ranked list
              ↓
    CV Viewer → BERT sentences highlighted yellow, matched skills highlighted green
```

### Why the 32 / 48 / 20 Split?

| Component | Weight | Rationale |
|-----------|--------|-----------|
| TF-IDF | 32% | Exact keyword presence — ensures required tech (React, MongoDB) appears verbatim |
| BERT | 48% | Semantic alignment — catches paraphrased experience and conceptual overlap |
| Quiz | 20% | Proven domain knowledge — validates the candidate actually understands the role |

Combined, the three components outperform any single signal alone (see `notebooks/04_model_comparison.ipynb`).

---

## Quiz System

HireIQ generates a unique quiz per job posting to measure practical knowledge alongside the resume.

### How It Works

1. **Generation** — When a recruiter publishes a job, the Gemini API asynchronously builds a pool of 15 questions derived from the job description and stores them in `quiz_pool`.
2. **Serving** — Candidates request `/quiz/<job_id>/start`. The system draws 15 random questions, **shuffles the answer order server-side**, and returns the sanitized quiz (no `correct_index`) along with a 10-minute countdown.
3. **Grading** — On `/quiz/<job_id>/submit`, the server compares answers to its saved session, enforcing the 10-minute time limit (+ 5s buffer). Tab-switch attempts are recorded for integrity (3 switches trigger auto-submit).
4. **Scoring integration** — The candidate's **best score** across attempts is used in the hybrid formula.

### Constraints

| Rule | Value |
|------|-------|
| Maximum attempts per candidate per job | 2 |
| Cooldown between attempts | 24 hours |
| Time limit | 10 minutes |
| Pass threshold | 12 / 15 |

---

## Candidate Application Tracking

Recruiters can track each candidate through a defined pipeline without leaving the app.

### Status Values

| Status | Meaning |
|--------|---------|
| `Under Review` | Default on upload |
| `Shortlisted` | Recruiter marked for further consideration |
| `Selected` | Offer extended / hired |
| `Rejected` | Application closed |

- Recruiters update status via `PUT /resumes/detail/<resume_id>/status`
- Candidates see their current status in real time at `GET /resumes/my-applications`

---

## Quick Start (Docker)

### Prerequisites
- Docker Desktop installed and running
- Google OAuth credentials (from Google Cloud Console)
- Google Gemini API key — *free tier at [aistudio.google.com](https://aistudio.google.com)*

### 1. Configure environment
```bash
cp .env .env.local
# Edit with your actual credentials:
nano .env
```

Required values:
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
GEMINI_API_KEY=your-gemini-api-key
FLASK_SECRET_KEY=change-this-random-string-32-chars
JWT_SECRET_KEY=another-random-32-char-string
MONGO_URI=mongodb://mongo:27017/hireiq
```

### 2. Start everything
```bash
docker-compose up --build
```

Wait ~2–3 minutes for models to download (BERT: ~80 MB, spaCy: ~40 MB).

### 3. Access the app

| Service | URL |
|---------|-----|
| App (Frontend + API) | http://localhost:5000 |
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
# → http://localhost:5000
```

> **No separate frontend server needed.**  
> Flask serves `app/templates/index.html` and all static assets at `/static/`.  
> The `catch_all` route in `app/__init__.py` forwards every unknown path to `index.html`,  
> enabling client-side routing via the HTML5 History API.

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
| DELETE | `/jobs/<id>` | ✅ | Delete job + associated resumes |

### Resumes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/resumes/<job_id>/upload` | ✅ | Upload PDF (multipart/form-data) |
| GET | `/resumes/<job_id>` | ✅ | List resumes for a job (recruiter) |
| GET | `/resumes/detail/<resume_id>` | ✅ | Full resume with raw text |
| PUT | `/resumes/detail/<resume_id>/status` | ✅ | Update application status (recruiter) |
| DELETE | `/resumes/detail/<resume_id>` | ✅ | Delete resume |
| GET | `/resumes/my-applications` | ✅ | Candidate's own applications and statuses |

### Ranking
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ranking/<job_id>` | ✅ | Run full AI ranking pipeline |
| GET | `/ranking/<job_id>/results` | ✅ | Get cached ranking results |
| GET | `/ranking/<job_id>/export/csv` | ✅ | Download ranked results as CSV |

### Quiz
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/quiz/<job_id>/start` | ✅ | Fetch 15 randomised questions (starts 10 min timer) |
| POST | `/quiz/<job_id>/submit` | ✅ | Submit answers, receive score and pass/fail |

### WebSocket
| Path | Description |
|------|-------------|
| `ws://localhost:5000/ws/ranking/<job_id>?token=<jwt>` | Live per-resume ranking feed |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | ✅ | Flask session signing key |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | ✅ | Must match Google Console exactly |
| `JWT_SECRET_KEY` | ✅ | JWT signing secret |
| `GEMINI_API_KEY` | ⚠️ | Gemini LLM + quiz generation (rule-based fallback if absent) |
| `JWT_ACCESS_EXPIRES_MINUTES` | ❌ | Default: 60 |
| `JWT_REFRESH_EXPIRES_DAYS` | ❌ | Default: 30 |
| `MAX_CONTENT_LENGTH` | ❌ | Default: 5242880 (5 MB) |

---

## Security Model

### PDF Upload — 4 Layers (Consolidated in `upload_security.py`)

| Layer | Check | What It Catches |
|-------|-------|-----------------|
| 1 | `validate_upload` | Extension `.pdf`, MIME `application/pdf`, size ≤ 5 MB |
| 2a | `verify_pdf_magic_bytes` | Binary header `%PDF-` — catches renamed executables |
| 2b | `inspect_pdf` (PyMuPDF) | JavaScript embeds, launch actions, embedded executables |
| 3 | `sanitize_filename` | Discards original filename, assigns UUID4 — prevents path traversal |

> All four functions live in a single consolidated module: `app/security/upload_security.py`

### Auth Security
- Google OAuth 2.0 with CSRF state token verification
- JWT signed with HS256; short-lived access tokens (60 min)
- Long-lived refresh tokens (30 days) for seamless re-auth
- Middleware (`require_auth`) validates JWT on every protected route

### Quiz Integrity
- Answer keys stored **server-side only** — never sent to the browser
- Answers shuffled per-session on the server before dispatch
- 10-minute timer enforced server-side (client timer is visual only)
- Tab-switch count logged per attempt for recruiter visibility (3 switches trigger auto-submit)

---

## Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| F1 | Google OAuth login | ✅ `/auth/login` + `/auth/callback` |
| F2 | Job CRUD | ✅ `/jobs/*` endpoints |
| F3 | PDF upload with 4-layer security | ✅ `app/security/upload_security.py` |
| F4 | Text extraction from PDF | ✅ PyMuPDF in `inspect_pdf()` |
| F5 | TF-IDF keyword score | ✅ `tfidf_model.py` |
| F6 | BERT semantic score | ✅ `bert_model.py` |
| F7 | Hybrid final score (TF-IDF + BERT + Quiz) | ✅ `hybrid_scorer.py` (32/48/20) |
| F8 | Matched / missing skills | ✅ `skill_extractor.py` |
| F9 | Gemini AI explanation | ✅ `llm_explainer.py` (Gemini 2.5 Flash) |
| F10 | Live WebSocket ranking | ✅ `ws_ranking.py` + `renderJobApplicants()` in `app.js` |
| F11 | Applicant score display (hybrid / quiz / TF-IDF / BERT) | ✅ `renderResultsList()` in `app.js` |
| F12 | CSV export (includes quiz score) | ✅ `/ranking/<id>/export/csv` |
| F13 | Skill & sentence highlighting in CV view | ✅ `renderResumeView()` in `app.js` (green = skills, yellow = BERT sentences) |
| F14 | AI-generated quiz per job | ✅ `quiz_generator.py` + `/quiz/*` routes |
| F15 | Quiz attempt limits & timer enforcement | ✅ `quiz.py` route (server-side) |
| F16 | Random Forest hiring prediction | ✅ `rf_predictor.py` + `trained_models/` |
| F17 | Candidate application tracking | ✅ `/resumes/detail/<id>/status` |
| F18 | Candidate personal dashboard | ✅ `/resumes/my-applications` |

---

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `00_train_random_forest.ipynb` | Trains `random_forest_v1.pkl` on `hr_hiring_dataset.csv` — the ML hiring predictor (**run this first**) |
| `01_tfidf_baseline.ipynb` | N-gram range comparison, `sublinear_tf` effect, top keyword extraction, score distribution on real dataset |
| `02_bert_semantic.ipynb` | Cosine heatmap, PCA embedding visualisation, per-sentence scoring demo, threshold sensitivity, CPU benchmark |
| `03_skill_extraction.ipynb` | spaCy NER vs noun chunk breakdown, skill gap bar chart, spaCy vs regex comparison |
| `04_model_comparison.ipynb` | TF-IDF vs BERT vs Quiz vs Hybrid side-by-side, radar charts per candidate, weight sensitivity analysis |
| `05_final_model.ipynb` | RF feature importance, end-to-end pipeline validation, final ranking chart, graceful degradation test |

Run with:
```bash
cd resume-analyzer && jupyter lab notebooks/
```

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

### Gemini API returns empty explanation
Check `GEMINI_API_KEY` is set correctly in `.env`. The system automatically falls back to a rule-based explanation if the key is missing or the API is unavailable.

### Quiz not available after job creation
Quiz generation is asynchronous. Wait a few seconds and retry `/quiz/<job_id>/start`. If still unavailable, check `GEMINI_API_KEY` — the quiz pool requires a valid key.

### Random Forest model not found
If `trained_models/random_forest_v1.pkl` is missing, `rf_predictor.py` gracefully falls back to a weighted formula using TF-IDF, BERT, and skill match count.

---

## License

CSG3101 Applied Project — Academic Use Only
