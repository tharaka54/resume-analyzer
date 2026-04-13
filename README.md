# HireIQ — AI-Powered Resume Analyzer & Ranking System

<br/>
<img src="app/static/img/logo.png" alt="HireIQ Logo" width="150" style="border-radius: 10px;" />

> An intelligent end-to-end recruitment platform that scores, ranks, and explains candidate resumes using a multi-signal AI pipeline — combining TF-IDF keyword matching, BERT semantic similarity, an AI-generated quiz, and a Random Forest hiring predictor, with plain-English explanations powered by Google Gemini.
>
> **Zero build step.** The frontend is a **vanilla HTML + JavaScript SPA** served directly by Flask — no React, no npm, no bundler required.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [AI Scoring Pipeline](#ai-scoring-pipeline)
4. [Quiz System](#quiz-system)
5. [Candidate Application Tracking](#candidate-application-tracking)

6. [Local Development](#local-development)
7. [API Reference](#api-reference)
8. [Environment Variables](#environment-variables)
9. [Security Model](#security-model)
10. [Functional Requirements](#functional-requirements)
11. [Notebooks](#notebooks)

---

## Overview

HireIQ is a full-stack recruitment tool with **two user roles**:

### For Recruiters
1. **Create job postings** with a full description
2. **Upload candidate PDFs** through a consolidated 5-layer security pipeline
3. **Generate AI quizzes** automatically from the job description via Gemini
4. **Run AI ranking** in real-time via WebSocket with live per-resume progress
5. **View multi-dimensional scores** including hybrid, quiz, TF-IDF, and BERT scores
6. **Read plain-English AI explanations** powered by Google Gemini 2.5 Flash
7. **Update candidate status** (Under Review → Shortlisted → Selected → Rejected)
8. **Export rankings** to CSV in one click

### For Candidates
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
| Security | PyMuPDF, 5-layer PDF/input validation (`upload_security.py`, `antivirus.py`, `input_sanitizer.py`) |
| Rate Limiting | Flask-Limiter (`app/extensions.py`) — per-route IP/user limits |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│            Vanilla HTML/JS SPA  (Flask serves index.html)            │
│  app/templates/index.html  +  app/static/js/app.js                  │
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
│  /resumes/* PDF upload (5-layer security) + tracking + my-apps      │
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
[5-Layer Security — upload_security.py + antivirus.py + input_sanitizer.py]
  Layer 1  →  Extension (.pdf), MIME, size ≤ 5 MB
  Layer 2a →  Magic bytes  (%PDF- binary header)
  Layer 2b →  PyMuPDF deep scan  (JS, launch actions, embedded execs)
  Layer 3  →  UUID4 rename  (path traversal guard)
  Layer 4  →  Input sanitization  (HTML strip, NoSQL injection guard)
  Layer 5  →  Antivirus scan  (entropy heuristic + VirusTotal API)
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
- Each application also exposes a `journey_status` field showing the candidate's pipeline stage (e.g. "Quiz Passed → CV Uploaded → Under Review")



## Local Development

### Backend (Flask)
```bash
# Create virtual environment
py -m venv venv
.\venv\Scripts\activate        # Windows
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
| POST | `/jobs/` | Yes | Create job posting |
| GET | `/jobs/` | Yes | List all jobs |
| GET | `/jobs/<id>` | Yes | Get single job |
| PUT | `/jobs/<id>` | Yes | Update job |
| DELETE | `/jobs/<id>` | Yes | Delete job + associated resumes |

### Resumes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/resumes/<job_id>/upload` | Yes | Upload PDF (multipart/form-data) |
| GET | `/resumes/<job_id>` | Yes | List resumes for a job (recruiter) |
| GET | `/resumes/detail/<resume_id>` | Yes | Full resume with raw text |
| PUT | `/resumes/detail/<resume_id>/status` | Yes | Update application status (recruiter) |
| DELETE | `/resumes/detail/<resume_id>` | Yes | Delete resume |
| GET | `/resumes/my-applications` | Yes | Candidate's own applications and statuses |

### Ranking
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ranking/<job_id>` | Yes | Run full AI ranking pipeline |
| GET | `/ranking/<job_id>/results` | Yes | Get cached ranking results |
| GET | `/ranking/<job_id>/export/csv` | Yes | Download ranked results as CSV |

### Quiz
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/quiz/<job_id>/start` | Yes | Fetch 15 randomised questions (starts 10 min timer) |
| POST | `/quiz/<job_id>/submit` | Yes | Submit answers, receive score and pass/fail |

### WebSocket
| Path | Description |
|------|-------------|
| `ws://localhost:5000/ws/ranking/<job_id>?token=<jwt>` | Live per-resume ranking feed |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | Flask session signing key |
| `MONGO_URI` | Yes | MongoDB connection string |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Yes | Must match Google Console exactly |
| `JWT_SECRET_KEY` | Yes | JWT signing secret |
| `GEMINI_API_KEY` | Optional | Gemini LLM + quiz generation (rule-based fallback if absent) |
| `VIRUSTOTAL_API_KEY` | Optional | VirusTotal API for Layer 5 antivirus scan (skipped if not set) |
| `JWT_ACCESS_EXPIRES_MINUTES` | Optional | Default: 60 |
| `JWT_REFRESH_EXPIRES_DAYS` | Optional | Default: 30 |
| `MAX_CONTENT_LENGTH` | Optional | Default: 5242880 (5 MB) |

---

## Security Model

### PDF Upload — 5 Layers

| Layer | Module | Check | What It Catches |
|-------|--------|-------|-----------------|
| 1 | `upload_security.py` | `validate_upload` | Extension `.pdf`, MIME `application/pdf`, size ≤ 5 MB |
| 2a | `upload_security.py` | `verify_pdf_magic_bytes` | Binary header `%PDF-` — catches renamed executables |
| 2b | `upload_security.py` | `inspect_pdf` (PyMuPDF) | JavaScript embeds, launch actions, embedded executables |
| 3 | `upload_security.py` | `sanitize_filename` | Discards original filename, assigns UUID4 — prevents path traversal |
| 4 | `input_sanitizer.py` | `sanitize_status_payload` | HTML/XSS stripping, NoSQL operator injection guard (`$where`, `$gt`, etc.) |
| 5 | `antivirus.py` | `scan_file_for_malware` | SHA-256 blocklist + Shannon entropy heuristic + VirusTotal API (optional) |

### Rate Limiting (Flask-Limiter via `app/extensions.py`)

| Route | Limit |
|-------|-------|
| `POST /auth/login` | 3 per minute per IP |
| `GET /auth/callback` | 3 per minute per IP |
| `GET /quiz/*/start` | 5 per minute per IP |
| `POST /quiz/*/submit` | 5 per minute per IP |
| `POST /jobs/` | 10 per hour per user |
| `POST /resumes/*/upload` | 20 per hour per user |

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
| F1 | Google OAuth login | Done — `/auth/login` + `/auth/callback` |
| F2 | Job CRUD | Done — `/jobs/*` endpoints |
| F3 | PDF upload with 5-layer security | Done — `app/security/upload_security.py`, `antivirus.py`, `input_sanitizer.py` |
| F4 | Text extraction from PDF | Done — PyMuPDF in `inspect_pdf()` |
| F5 | TF-IDF keyword score | Done — `tfidf_model.py` |
| F6 | BERT semantic score | Done — `bert_model.py` |
| F7 | Hybrid final score (TF-IDF + BERT + Quiz) | Done — `hybrid_scorer.py` (32/48/20) |
| F8 | Matched / missing skills | Done — `skill_extractor.py` |
| F9 | Gemini AI explanation | Done — `llm_explainer.py` (Gemini 2.5 Flash) |
| F10 | Live WebSocket ranking | Done — `ws_ranking.py` + `renderJobApplicants()` in `app.js` |
| F11 | Applicant score display (hybrid / quiz / TF-IDF / BERT) | Done — `renderResultsList()` in `app.js` |
| F12 | CSV export (includes quiz score) | Done — `/ranking/<id>/export/csv` |
| F13 | Skill & sentence highlighting in CV view | Done — `renderResumeView()` in `app.js` (green = skills, yellow = BERT sentences) |
| F14 | AI-generated quiz per job | Done — `quiz_generator.py` + `/quiz/*` routes |
| F15 | Quiz attempt limits & timer enforcement | Done — `quiz.py` route (server-side) |
| F16 | Random Forest hiring prediction | Done — `rf_predictor.py` + `trained_models/` |
| F17 | Candidate application tracking | Done — `/resumes/detail/<id>/status` |
| F18 | Candidate personal dashboard | Done — `/resumes/my-applications` |
| F19 | Rate limiting on sensitive endpoints | Done — Flask-Limiter in `app/extensions.py` |
| F20 | NoSQL injection & XSS input sanitization | Done — `app/security/input_sanitizer.py` |
| F21 | Antivirus / VirusTotal scan on upload | Done — `app/security/antivirus.py` |

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

## License

Academic Use Only

---

## Academic Supervision

This project was guided and supervised by Ann Roshanie Appuhamy as part of undergraduate coursework.
