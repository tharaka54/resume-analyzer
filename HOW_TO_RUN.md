# How to Run: HireIQ - AI Resume Analyzer & Ranking System

This guide outlines exactly what tools you need, the prerequisites to configure, and the step-by-step process of starting the system on your machine.

---

## 1. Prerequisites (Tools Required)
To run this application, you must have the following software installed on your computer:
1. **Python 3.11** or higher.
2. **MongoDB 7.0+** (Either installed locally as a service or a free cloud cluster via MongoDB Atlas).
3. **Git** (For version control, optional).
4. **Jupyter** (If you intend to retrain the ML model via the provided notebooks).

## 2. External API Keys Needed
Before running the server, you must generate three external connection keys:

1. **Google OAuth 2.0 Credentials (For User Login)**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project and setup the OAuth consent screen.
   - Create OAuth Client ID credentials (Web Application).
   - Set the `Authorized redirect URIs` to exactly: `http://localhost:5000/auth/callback`.
   - Save the **Client ID** and **Client Secret**.

2. **Google Gemini API Key (For AI Quiz & Explainer)**
   - Go to [Google AI Studio](https://aistudio.google.com/).
   - Generate a free API key.

## 3. Environment Variable Configuration
The system uses a `.env` file to manage secrets securely. 
1. Create a file named `.env` in the root `resume-analyzer` directory.
2. Populate the file with the following variables:

```env
# Flask runtime configuration
FLASK_SECRET_KEY=generate_a_random_32_character_string
FLASK_ENV=development
FLASK_DEBUG=True

# Database Connection (Update if using MongoDB Atlas)
MONGO_URI=mongodb://localhost:27017/resume_analyzer

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback

# Security & JWT Tokens
JWT_SECRET_KEY=generate_another_random_32_character_string
JWT_ACCESS_EXPIRES_MINUTES=60
JWT_REFRESH_EXPIRES_DAYS=30

# Gemini AI Key
GEMINI_API_KEY=your-gemini-api-key-here

# File Upload Rules
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=5242880
```

*Note: You can generate safe random strings for `FLASK_SECRET_KEY` and `JWT_SECRET_KEY` by running this in your terminal:*
`python -c "import secrets; print(secrets.token_hex(32))"`

---

## 4. Local Setup & Execution Guide
Once your `.env` is ready, follow these exact steps to start the platform.

### Step 1: Initialize the Database
Ensure your MongoDB server is actively running in the background. If you installed it locally, check that the `MongoDB` service is active on port `27017`.

### Step 2: Create a Virtual Environment
We highly recommend using a virtual environment to isolate dependencies.
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies
With the virtual environment activated, install all backend packages:
```bash
pip install -r requirements.txt
```

### Step 4: Download NLP Models
The system uses `spaCy` for Natural Language Processing rule extraction. You must download the English model before running:
```bash
python -m spacy download en_core_web_md
```
*(Note: During the first run of the app, `sentence-transformers` will also automatically download a ~80MB BERT model to your local cache. This may take a minute.)*

### Step 5: Start the Flask Server
Since this app is a monolith that uses Vanilla HTML/JS directly served through Flask, you do **not** need a separate frontend server (No npm, React, Vue, or Vite required!).

Start the backend (which also serves the frontend):
```bash
python run.py
```

### Step 6: Access the Application
The server will bind to port `5000`. 
Open your browser and navigate to: **[http://localhost:5000](http://localhost:5000)**

---

## 5. First-Time Model Training (Optional, if missing)
If the pre-trained `random_forest_v1.pkl` file is missing from the `trained_models` directory, the system will fall back to rule-based logic. To regenerate the model:
1. Open a new terminal.
2. Run `jupyter lab notebooks/`
3. Open `00_train_random_forest.ipynb` and run all cells. 
4. The `.pkl` file will automatically be saved and picked up by the backend.

---
## Summary of Startup Architecture
- **Port 5000:** Handles REST API routes, HTML/JS serving, and WebSocket live-ranking feeds.
- **Port 27017:** Interacts with the local MongoDB database. 
- **Google Cloud/AI Studio:** External HTTP connections to validate OAuth logins and hit Gemini for AI processing.
