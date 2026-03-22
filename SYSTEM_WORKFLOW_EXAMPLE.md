# End-to-End System Workflow Example: How HireIQ Works

This document provides a concrete, step-by-step example of how data flows through the HireIQ platform—from the moment a job is posted, to the AI ranking, down to the final recruiter decision.

---

## The Scenario
- **Recruiter:** Alice (Engineering Manager at DataCorp)
- **Candidate:** Bob (Software Engineer)
- **Job Posting:** Senior Backend Developer

---

### Phase 1: Job Creation & Dynamic Quiz Generation
1. **Action:** Alice logs in via Google OAuth and creates a new job posting for a "Senior Backend Developer". She lists required skills: `Python, Flask, MongoDB, Docker, AWS`.
2. **AI Action:** The moment Alice clicks submit, the backend asynchronously contacts the **Google Gemini 2.5 Flash API**.
3. **Output:** Gemini dynamically reads the job description and generates a structured JSON array of 15 targeted, multiple-choice technical questions specific to Python, Flask, and AWS. This pool is saved securely in the database (`quiz_pool`).

---

### Phase 2: Candidate Pre-Screening (The Quiz Wall)
1. **Action:** Bob browses the public job board, clicks Alice's job, and clicks "Apply". He is greeted by the AI pre-screening quiz.
2. **System Security Protocol:**
   - The system draws the 15 questions, but **shuffles the answer order (A, B, C, D)** server-side so Bob gets a unique variant.
   - The correct answers are **never** transmitted to Bob's browser to prevent inspection tools from scraping the answers.
   - A **10-minute server-side timer** begins.
3. **Action:** Bob answers the questions. During the test, he switches tabs twice to look up a Flask command. The system detects and silently logs these tab switches.
4. **Grading:** Bob submits. He scores **13/15**. Because the passing threshold is 12, he passes and unlocks the CV Upload portal. (If he failed, he would be locked out for 24 hours).

---

### Phase 3: The 4-Layer Security Upload
1. **Action:** Bob uploads his resume (`bob_resume_v2.pdf`).
2. **Security Pipeline (`upload_security.py`):** Before the file ever touches the disk, it passes through 4 layers of defense:
   - **Layer 1:** Validates the MIME type is `application/pdf` and file size < 5 MB.
   - **Layer 2a (Magic Bytes):** Checks the binary header (`%PDF-`) to ensure it's not a renamed malicious executable.
   - **Layer 2b (Deep Scan):** Uses `PyMuPDF` to parse the PDF document structure, looking for embedded JavaScript or automatic launch actions.
   - **Layer 3 (Sanitization):** The file is renamed to a random UUID (e.g., `a7f3-42bc.pdf`) to destroy any path traversal attempts (`../`) in the original filename.
3. **Storage:** The text is extracted completely by `PyMuPDF` and saved to `MongoDB`. Bob's status is set to `Under Review`.

---

### Phase 4: Machine Learning & NLP Ranking
1. **Action:** Alice goes to her Recruiter Dashboard and clicks "Score New Applications".
2. **Live Feed:** A WebSocket connection opens, processing all new resumes and streaming a live progress bar to Alice's screen.

**Behind the scenes for Bob's CV, the `hybrid_scorer.py` engine executes:**

#### A. TF-IDF Keyword Scoring (32% Weight)
- Calculates term frequency against the job description.
- Bob explicitly wrote "Python", "Flask", and "MongoDB", giving him a strong exact-match score.
- **Score:** 85%

#### B. BERT Semantic Matching (48% Weight)
- Uses HuggingFace's `all-MiniLM-L6-v2` transformer model.
- BERT understands *meaning*, not just words. For example, if the job description asks for "Cloud Infrastructure" and Bob wrote "Deployed serverless clusters and S3 buckets", TF-IDF might miss it, but BERT identifies the high conceptual overlap.
- **Score:** 92%

#### C. Skill Gap Extraction (spaCy NER)
- Uses `spaCy` to run Named Entity Recognition over the text to pull out proper nouns and technical jargon.
- **Matched:** `Python, Flask, MongoDB, AWS`. **Missing:** `Docker`.

#### D. The ML Hiring Predictor (`rf_predictor.py`)
- The system feeds Bob's TF-IDF score, BERT score, and Skill Match count into a pre-trained **Random Forest Machine Learning Model** (`random_forest_v1.pkl`).
- This model was trained on thousands of historical HR datasets to predict actual hiring outcomes.
- **Model Output:** `Prediction: HIRED`, `Probability: 86%`.

#### E. Plain-English Summary (Gemini LLM)
- The system sends the raw scores and CV text back to Google Gemini, asking it to write a 2-paragraph summary for Alice.
- **Gemini Outputs:** *"Bob is a highly compatible candidate. His semantic overlap in backend infrastructure is excellent, and his quiz score proves practical knowledge of Python. His only notable skill gap is Docker, which may require brief onboarding."*

---

### Phase 5: Recruiter Review & Verdict
1. **Action:** Alice looks at her ranked dashboard. Bob is ranked #1 with an overall Hybrid Score of 88%.
2. **Action:** Alice clicks "View Highlighted CV".
   - The UI loads Bob's raw text.
   - **Green Highlights:** Explicitly matched skills (e.g., Python, AWS).
   - **Yellow Highlights:** Entire sentences that BERT flagged as conceptually highly relevant to the job description.
3. **Verdict:** Alice reads the AI summary, confirms the yellow highlights, and clicks the green **"Accept"** button.

---

### Phase 6: Candidate Tracking
1. **Action:** Bob logs into the platform to check the status of his applications.
2. **Action:** On his "My Applications" dashboard, he sees the "Senior Backend Developer" role.
3. **Outcome:** The text has changed from `Under Review` to an exciting green `Selected` label. The AI pipeline successfully bridged the gap between Alice's technical requirements and Bob's proven capabilities!
