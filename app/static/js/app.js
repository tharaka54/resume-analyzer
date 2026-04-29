document.addEventListener("DOMContentLoaded", () => {
    const mainContent = document.getElementById("main-content");
    const loginBtn = document.getElementById("login-btn");
    const navLinks = document.getElementById("nav-links");

    let quizTimerInterval;
    let tabSwitches = 0;
    let isTakingQuiz = false;

    // Visibility change detection for Anti-cheat
    document.addEventListener("visibilitychange", () => {
        if (isTakingQuiz && document.hidden) {
            tabSwitches++;
            alert(`WARNING: Tab switch detected! (${tabSwitches}/3)`);
            if (tabSwitches >= 3) {
                alert("Maximum tab switches reached. Quiz will be auto-submitted.");
                document.getElementById('submit-quiz-btn').click();
            }
        }
    });

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("login_success") === "1") {
        const token = urlParams.get("access_token");
        const name = urlParams.get("name");
        localStorage.setItem("token", token);
        localStorage.setItem("user_name", name);
        window.history.replaceState({}, document.title, "/");
    }

    const token = localStorage.getItem("token");
    const userName = localStorage.getItem("user_name");

    if (token) {
        loginBtn.style.display = 'none';
        const userSpan = document.createElement("span");
        userSpan.textContent = `Welcome, ${userName}`;
        userSpan.style.marginRight = "15px";

        const logoutBtn = document.createElement("button");
        logoutBtn.id = "logout-btn";
        logoutBtn.textContent = "Logout";
        logoutBtn.style.backgroundColor = "#dc3545";
        logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("token");
            localStorage.removeItem("user_name");
            window.location.href = "/";
        });

        const myJobsLink = document.createElement("a");
        myJobsLink.href = "/dashboard";
        myJobsLink.setAttribute("data-link", "");
        myJobsLink.textContent = "My Dashboard";

        const postJobLink = document.createElement("a");
        postJobLink.href = "/post-job";
        postJobLink.setAttribute("data-link", "");
        postJobLink.textContent = "Post a Job";

        const myAppsLink = document.createElement("a");
        myAppsLink.href = "/my-applications";
        myAppsLink.setAttribute("data-link", "");
        myAppsLink.textContent = "My Applications";

        navLinks.appendChild(postJobLink);
        navLinks.appendChild(myAppsLink);
        navLinks.appendChild(myJobsLink);
        navLinks.appendChild(userSpan);
        navLinks.appendChild(logoutBtn);
    } else {
        loginBtn.addEventListener("click", () => {
            localStorage.setItem("redirect_after_login", window.location.pathname);
            window.location.href = "/auth/login";
        });
    }

    function loadContent(route) {
        // Clear quiz timer if navigating away
        clearInterval(quizTimerInterval);
        isTakingQuiz = false;
        tabSwitches = 0;

        if (route === "/") {
            renderHomepage();
        } else if (route === "/my-applications") {
            if (!token) return navigateToLogin();
            renderMyApplications();
        } else if (route === "/dashboard") {
            if (!token) return navigateToLogin();
            renderDashboard();
        } else if (route === "/post-job") {
            if (!token) return navigateToLogin();
            renderPostJob();
        } else if (route.startsWith("/edit-job/")) {
            if (!token) return navigateToLogin();
            const jobId = route.split("/")[2];
            renderEditJob(jobId);
        } else if (route.startsWith("/job/")) {
            const jobId = route.split("/")[2];
            renderJobDetails(jobId);
        } else if (route.startsWith("/job-quiz/")) {
            if (!token) return navigateToLogin();
            const jobId = route.split("/")[2];
            renderJobQuiz(jobId);
        } else if (route.startsWith("/quiz/")) {
            if (!token) return navigateToLogin();
            const jobId = route.split("/")[2];
            renderQuizPage(jobId);
        } else if (route.startsWith("/upload-cv/")) {
            if (!token) return navigateToLogin();
            const jobId = route.split("/")[2];
            renderCVUpload(jobId);
        } else if (route.startsWith("/job-applicants/")) {
            if (!token) return navigateToLogin();
            const jobId = route.split("/")[2];
            renderJobApplicants(jobId);
        } else if (route.startsWith("/resume-view/")) {
            if (!token) return navigateToLogin();
            const resumeId = route.split("/")[2];
            renderResumeView(resumeId);
        } else {
            mainContent.innerHTML = `<h2>404 Not Found</h2><p>Page does not exist.</p>`;
        }
    }

    function navigateToLogin() {
        localStorage.setItem("redirect_after_login", window.location.pathname);
        window.location.href = "/auth/login";
    }

    window.deleteJob = async (jobId) => {
        if (!confirm("Are you sure you want to delete this job and all its applications?")) return;
        try {
            const res = await fetch(`/jobs/${jobId}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${localStorage.getItem('token')}` }
            });
            if (res.ok) {
                alert("Job deleted successfully.");
                loadContent('/dashboard');
            } else {
                const data = await res.json();
                alert("Error: " + data.error);
            }
        } catch (e) {
            alert("Request failed.");
        }
    };

    window.editJob = async (jobId) => {
        window.history.pushState(null, '', `/edit-job/${jobId}`);
        loadContent(`/edit-job/${jobId}`);
    };

    window.updateStatus = async (resumeId, status) => {
        try {
            const res = await fetch(`/resumes/detail/${resumeId}/status`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ status })
            });
            if (res.ok) {
                alert(`Status updated to ${status}`);
                loadContent(window.location.pathname);
            } else {
                const data = await res.json();
                alert("Failed to update status: " + (data.error || 'Unknown error'));
            }
        } catch (e) { 
            alert("Error occurred while updating status"); 
        }
    };

    // --- PAGE RENDERERS ---

    function renderHomepage() {
        mainContent.innerHTML = `
            <h2>Public Job Listings</h2>
            <div class="search-bar">
                <input type="text" id="search-input" placeholder="Search by job title or company...">
                <button class="primary-btn" id="search-btn">Search</button>
            </div>
            <div style="margin-bottom: 20px;">
                <label>Filter by type: </label>
                <select id="filter-type" style="padding: 5px; margin-right: 10px;">
                    <option value="">All</option>
                    <option value="Full-Time">Full-Time</option>
                    <option value="Part-Time">Part-Time</option>
                    <option value="Contract">Contract</option>
                </select>
                <button id="reset-filter-btn" style="padding: 5px;">Reset</button>
            </div>
            <div id="job-list" class="job-list">Loading jobs...</div>
        `;

        fetch("/jobs/public").then(r => r.json()).then(data => {
            const jobList = document.getElementById("job-list");
            let allJobs = data.jobs || [];

            function renderJobs(jobsToRender) {
                if (jobsToRender && jobsToRender.length > 0) {
                    jobList.innerHTML = jobsToRender.map(job => `
                        <div class="job-card" onclick="window.history.pushState(null, '', '/job/${job._id}'); window.dispatchEvent(new Event('popstate'))">
                            <h3>${job.title}</h3>
                            <p class="company">${job.company || 'Unknown Company'}</p>
                            <div class="tags">
                                <span class="tag">${job.location || 'Remote'}</span>
                                <span class="tag">${job.job_type || 'Full-Time'}</span>
                            </div>
                        </div>
                    `).join("");
                } else {
                    jobList.innerHTML = "<p>No jobs available.</p>";
                }
            }

            renderJobs(allJobs);

            function handleSearch() {
                const query = document.getElementById("search-input").value.toLowerCase();
                const typeFilter = document.getElementById("filter-type").value;
                const filtered = allJobs.filter(j => {
                    const matchQuery = (j.title || "").toLowerCase().includes(query) || (j.company || "").toLowerCase().includes(query);
                    const matchType = typeFilter ? j.job_type === typeFilter : true;
                    return matchQuery && matchType;
                });
                renderJobs(filtered);
            }

            document.getElementById("search-btn").addEventListener("click", handleSearch);
            document.getElementById("filter-type").addEventListener("change", handleSearch);
            document.getElementById("reset-filter-btn").addEventListener("click", () => {
                document.getElementById("search-input").value = "";
                document.getElementById("filter-type").value = "";
                renderJobs(allJobs);
            });
            document.getElementById("search-input").addEventListener("keypress", (e) => {
                if (e.key === "Enter") handleSearch();
            });
        });
    }

    async function renderJobDetails(jobId) {
        mainContent.innerHTML = `<p>Loading job details...</p>`;
        try {
            const res = await fetch(`/jobs/public/${jobId}`);
            if (!res.ok) throw new Error("Job not found");
            const job = await res.json();

            mainContent.innerHTML = `
                <div class="job-details">
                    <button class="back-btn" onclick="window.history.back()">← Back to Jobs</button>
                    <h2>${job.title}</h2>
                    <h3 class="company">${job.company}</h3>
                    <div class="tags" style="margin-bottom: 20px;">
                        <span class="tag">${job.location || 'Remote'}</span>
                        <span class="tag">${job.job_type || 'Full-Time'}</span>
                    </div>
                    <p><strong>Required Skills:</strong> ${job.required_skills}</p>
                    <div class="description" style="white-space: pre-wrap;">${job.description}</div>
                    
                    <button id="apply-btn" class="primary-btn" style="margin-top: 20px;">Apply for this Job</button>
                </div>
            `;

            document.getElementById("apply-btn").addEventListener("click", () => {
                if (!token) {
                    navigateToLogin();
                } else {
                    window.history.pushState(null, '', `/quiz/${jobId}`);
                    loadContent(`/quiz/${jobId}`);
                }
            });

        } catch (err) {
            mainContent.innerHTML = `<p>Error loading job details.</p>`;
        }
    }

    function renderPostJob() {
        mainContent.innerHTML = `
            <h2>Post a New Job</h2>
            <form id="post-job-form" class="form-container">
                <input type="text" id="j-title" placeholder="Job Title" required>
                <input type="text" id="j-company" placeholder="Company Name" required>
                <input type="text" id="j-location" placeholder="Location e.g. London / Remote" required>
                <select id="j-type" required style="width:100%; padding:10px; margin-bottom:15px; border-radius:4px; border:1px solid #ccc;">
                    <option value="" disabled selected>Select Job Type</option>
                    <option value="Full-Time">Full-Time</option>
                    <option value="Part-Time">Part-Time</option>
                    <option value="Contract">Contract</option>
                </select>
                <input type="text" id="j-skills" placeholder="Required Skills (comma separated)" required>
                <textarea id="j-desc" placeholder="Job Description (at least 50 chars)" rows="8" required style="width:100%; padding:10px; margin-bottom:15px; border-radius:4px; border:1px solid #ccc;"></textarea>
                <button type="submit" class="primary-btn">Post Job & Generate AI Quiz</button>
            </form>
        `;

        document.getElementById("post-job-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector("button");
            btn.textContent = "Posting & Generating Quiz...";
            btn.disabled = true;

            const payload = {
                title: document.getElementById("j-title").value,
                company: document.getElementById("j-company").value,
                location: document.getElementById("j-location").value,
                job_type: document.getElementById("j-type").value,
                required_skills: document.getElementById("j-skills").value,
                description: document.getElementById("j-desc").value
            };

            try {
                const res = await fetch("/jobs/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    alert("Job posted! AI is generating the quiz pool in the background.");
                    window.history.pushState(null, '', '/dashboard');
                    loadContent('/dashboard');
                } else {
                    const data = await res.json();
                    alert("Error: " + data.error);
                    btn.textContent = "Post Job & Generate AI Quiz";
                    btn.disabled = false;
                }
            } catch (err) {
                alert("Request failed.");
                btn.textContent = "Post Job & Generate AI Quiz";
                btn.disabled = false;
            }
        });
    }

    async function renderEditJob(jobId) {
        mainContent.innerHTML = `<p>Loading job data...</p>`;
        try {
            const res = await fetch(`/jobs/${jobId}`, { headers: { "Authorization": `Bearer ${token}` } });
            if (!res.ok) throw new Error("Job not found");
            const job = await res.json();

            mainContent.innerHTML = `
                <h2>Edit Job</h2>
                <form id="edit-job-form" class="form-container">
                    <input type="text" id="j-title" value="${job.title}" required>
                    <input type="text" id="j-company" value="${job.company}" required>
                    <input type="text" id="j-location" value="${job.location || ''}" required>
                    <select id="j-type" required style="width:100%; padding:10px; margin-bottom:15px; border-radius:4px; border:1px solid #ccc;">
                        <option value="Full-Time" ${job.job_type === 'Full-Time' ? 'selected' : ''}>Full-Time</option>
                        <option value="Part-Time" ${job.job_type === 'Part-Time' ? 'selected' : ''}>Part-Time</option>
                        <option value="Contract" ${job.job_type === 'Contract' ? 'selected' : ''}>Contract</option>
                    </select>
                    <input type="text" id="j-skills" value="${job.required_skills || ''}" required>
                    <textarea id="j-desc" rows="8" required style="width:100%; padding:10px; margin-bottom:15px; border-radius:4px; border:1px solid #ccc;">${job.description}</textarea>
                    <button type="submit" class="primary-btn">Save Changes</button>
                    <button type="button" class="back-btn" onclick="window.history.back()" style="margin-top: 10px; display: block;">Cancel</button>
                </form>
            `;

            document.getElementById("edit-job-form").addEventListener("submit", async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector("button[type=submit]");
                btn.textContent = "Saving...";
                btn.disabled = true;

                const payload = {
                    title: document.getElementById("j-title").value,
                    company: document.getElementById("j-company").value,
                    location: document.getElementById("j-location").value,
                    job_type: document.getElementById("j-type").value,
                    required_skills: document.getElementById("j-skills").value,
                    description: document.getElementById("j-desc").value
                };

                try {
                    const res = await fetch(`/jobs/${jobId}`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                        body: JSON.stringify(payload)
                    });

                    if (res.ok) {
                        alert("Job updated successfully!");
                        window.history.pushState(null, '', '/dashboard');
                        loadContent('/dashboard');
                    } else {
                        const data = await res.json();
                        alert("Error: " + data.error);
                        btn.textContent = "Save Changes";
                        btn.disabled = false;
                    }
                } catch (err) {
                    alert("Request failed.");
                    btn.textContent = "Save Changes";
                    btn.disabled = false;
                }
            });
        } catch (err) {
            mainContent.innerHTML = `<p>Error loading job details.</p>`;
        }
    }

    // --- QUIZ AND CV LOGIC ---

    async function renderQuizPage(jobId) {
        mainContent.innerHTML = `<p>Loading AI Assessment...</p>`;
        try {
            const res = await fetch(`/quiz/${jobId}/start`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const data = await res.json();

            if (!res.ok) {
                mainContent.innerHTML = `<h3>Assessment Unavailable</h3><p>${data.error}</p><button class="primary-btn" onclick="window.history.back()">Go Back</button>`;
                return;
            }

            isTakingQuiz = true;
            tabSwitches = 0;
            let timeLeft = data.timer_seconds;

            let questionsHTML = data.questions.map((q, i) => `
                <div class="question-block" style="margin-bottom: 20px; padding:15px; border:1px solid #ddd; border-radius:6px;">
                    <p><strong>Q${i + 1}: ${q.question}</strong></p>
                    ${q.options.map((opt, j) => `
                        <label style="display:block; margin-bottom:5px;">
                            <input type="radio" name="q${i}" value="${j}"> ${opt}
                        </label>
                    `).join('')}
                </div>
            `).join('');

            mainContent.innerHTML = `
                <div class="quiz-container">
                    <h2>AI Pre-Screening Quiz</h2>
                    <div id="quiz-timer" style="font-weight:bold; color:red; margin-bottom: 15px;">Time Left: 10:00</div>
                    <form id="quiz-form">
                        ${questionsHTML}
                        <button type="button" id="submit-quiz-btn" class="primary-btn">Submit Quiz</button>
                    </form>
                </div>
            `;

            quizTimerInterval = setInterval(() => {
                timeLeft--;
                const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                const s = (timeLeft % 60).toString().padStart(2, '0');
                document.getElementById('quiz-timer').textContent = `Time Left: ${m}:${s}`;

                if (timeLeft <= 0) {
                    clearInterval(quizTimerInterval);
                    alert("Time is up! Auto-submitting quiz.");
                    document.getElementById('submit-quiz-btn').click();
                }
            }, 1000);

            document.getElementById('submit-quiz-btn').addEventListener("click", () => {
                submitQuiz(jobId, data.questions.length);
            });

        } catch (err) {
            mainContent.innerHTML = `<p>Error loading quiz. Please try again later.</p>`;
        }
    }

    async function submitQuiz(jobId, numQuestions) {
        clearInterval(quizTimerInterval);
        isTakingQuiz = false;
        const btn = document.getElementById("submit-quiz-btn");
        if (btn) btn.disabled = true;

        let answers = [];
        for (let i = 0; i < numQuestions; i++) {
            const selected = document.querySelector(`input[name="q${i}"]:checked`);
            answers.push(selected ? parseInt(selected.value) : -1);
        }

        try {
            const res = await fetch(`/quiz/${jobId}/submit`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ answers, tab_switches: tabSwitches })
            });
            const data = await res.json();

            if (data.passed) {
                mainContent.innerHTML = `
                    <h2>Quiz Passed! 🎉</h2>
                    <p>You scored ${data.score}/${numQuestions}. You are now eligible to upload your CV.</p>
                    <button class="primary-btn" onclick="window.history.pushState(null, '', '/upload-cv/${jobId}'); window.dispatchEvent(new Event('popstate'))">Proceed to CV Upload</button>
                `;
            } else {
                mainContent.innerHTML = `
                    <h2>Quiz Failed ❌</h2>
                    <p>You scored ${data.score}/${numQuestions}. A score of 12 or above is required.</p>
                    <p>Please review the job description and try again in 24 hours (max 2 attempts).</p>
                    <button class="back-btn" onclick="window.history.pushState(null, '', '/'); window.dispatchEvent(new Event('popstate'))">Return to Job Listings</button>
                `;
            }

        } catch (err) {
            alert("Failed to submit quiz.");
            if (btn) btn.disabled = false;
        }
    }

    function renderCVUpload(jobId) {
        mainContent.innerHTML = `
            <h2>Upload Your CV</h2>
            <div class="form-container">
                <p>Please upload your CV in PDF format (max 5MB). The system will analyze your CV against the job requirements.</p>
                <input type="file" id="cv-file" accept="application/pdf" required style="margin-bottom: 20px;">
                <button id="upload-cv-btn" class="primary-btn">Submit Application</button>
                <div id="upload-status" style="margin-top:20px; font-weight:bold;"></div>
            </div>
        `;

        document.getElementById("upload-cv-btn").addEventListener("click", async () => {
            const fileInput = document.getElementById("cv-file");
            if (!fileInput.files[0]) return alert("Please select a PDF file.");

            const formData = new FormData();
            formData.append("resume", fileInput.files[0]);
            formData.append("job_id", jobId);

            const status = document.getElementById("upload-status");
            status.textContent = "Uploading & Analyzing... this may take a moment.";

            try {
                const res = await fetch(`/resumes/${jobId}/upload`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${token}` },
                    body: formData
                });
                const data = await res.json();

                if (res.ok) {
                    status.style.color = "green";
                    status.textContent = "Application submitted successfully! Recruiter will review your profile shortly.";
                } else {
                    status.style.color = "red";
                    status.textContent = "Error: " + data.error;
                }
            } catch (err) {
                status.style.color = "red";
                status.textContent = "Upload failed due to network error.";
            }
        });
    }

    function renderDashboard() {
        mainContent.innerHTML = `
            <h2>My Dashboard</h2>
            <div id="my-jobs">Loading...</div>
        `;

        fetch("/jobs/", { headers: { "Authorization": `Bearer ${token}` } })
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById("my-jobs");
                if (data.jobs && data.jobs.length > 0) {
                    container.innerHTML = data.jobs.map(job => `
                    <div class="job-card" style="margin-bottom: 10px;">
                        <h3>${job.title}</h3>
                        <p>Applicants: ${job.resume_count}</p>
                        <div style="margin-top: 10px;">
                            <button class="primary-btn" style="width: auto; display: inline-block; margin-right: 10px;" onclick="window.history.pushState(null, '', '/job-applicants/${job._id}'); window.dispatchEvent(new Event('popstate'))">View Applicants</button>
                            <button class="primary-btn" style="width: auto; display: inline-block; background-color: #17a2b8; margin-right: 10px;" onclick="window.history.pushState(null, '', '/job-quiz/${job._id}'); window.dispatchEvent(new Event('popstate'))">View Quiz</button>
                            <button class="primary-btn" style="width: auto; display: inline-block; background-color: #ffc107; color: black; margin-right: 10px;" onclick="window.editJob('${job._id}')">Edit</button>
                            <button class="primary-btn" style="width: auto; display: inline-block; background-color: #dc3545;" onclick="window.deleteJob('${job._id}')">Delete</button>
                        </div>
                    </div>
                `).join("");
                } else {
                    container.innerHTML = "<p>No jobs posted yet.</p>";
                }
            });
    }

    async function renderJobApplicants(jobId) {
        mainContent.innerHTML = `
            <button class="back-btn" onclick="window.history.pushState(null, '', '/dashboard'); window.dispatchEvent(new Event('popstate'))">← Back to Dashboard</button>
            <h2>Applicant Tracking</h2>
            <div id="ws-status" style="margin-bottom:20px; color: blue;">Checking results...</div>
            <div style="margin-bottom:20px;">
                <button id="start-ranking-btn" class="primary-btn">Score New Applications</button>
                <button id="export-csv-btn" class="primary-btn" style="background-color: #28a745;">Download CSV Export</button>
            </div>
            
            <div id="ranking-progress" style="display:none; margin-bottom: 20px;">
                <p id="ranking-msg">Scoring in progress...</p>
                <progress id="ranking-bar" max="100" value="0" style="width: 100%;"></progress>
            </div>

            <div id="applicants-list" class="job-list" style="display:flex; flex-direction:column; gap:15px;"></div>
        `;

        document.getElementById("export-csv-btn").addEventListener("click", () => {
            window.open(`/ranking/${jobId}/export/csv?token=${token}`, "_blank");
        });

        const loadResults = async () => {
            const res = await fetch(`/ranking/${jobId}/results`, { headers: { "Authorization": `Bearer ${token}` } });
            if (res.ok) {
                const data = await res.json();
                renderResultsList(data.results);
            }
        };
        await loadResults();

        document.getElementById("start-ranking-btn").addEventListener("click", () => {
            document.getElementById("ranking-progress").style.display = "block";

            // Start WS connection
            const wsUrl = `ws://${window.location.host}/ws/ranking/${jobId}?token=${token}`;
            const ws = new WebSocket(wsUrl);

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                const status = document.getElementById("ws-status");
                const bar = document.getElementById("ranking-bar");
                const msgEl = document.getElementById("ranking-msg");

                if (msg.event === "connected") {
                    status.textContent = `Connected: processing ${msg.total} resumes.`;
                } else if (msg.event === "progress") {
                    msgEl.textContent = `Scoring ${msg.candidate}... (${msg.index}/${msg.total})`;
                    bar.value = (msg.index / msg.total) * 100;
                } else if (msg.event === "complete") {
                    status.textContent = `Ranking complete for ${msg.total_ranked} candidates.`;
                    ws.close();
                    loadResults();
                } else if (msg.event === "error") {
                    status.style.color = "red";
                    status.textContent = "Error: " + msg.message;
                }
            };

            // Trigger ranking manually so WS catches it
            fetch(`/ranking/${jobId}`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` }
            });
        });
    }

    function renderResultsList(results) {
        const list = document.getElementById("applicants-list");
        if (!results || results.length === 0) {
            list.innerHTML = "<p>No ranked applicants yet.</p>";
            return;
        }

        list.innerHTML = results.map((r, i) => `
            <div class="job-card" style="display:flex; flex-direction:column; align-items:flex-start;">
                <h3>#${i + 1} - ${r.candidate_name} <span style="font-size:0.8em; color:gray;">(${r.status || 'Under Review'})</span></h3>
                <p><strong>Hybrid Score:</strong> ${r.hybrid_score}% (Quiz: ${r.quiz_score}% | TFIDF: ${r.tfidf_score}% | BERT: ${r.bert_score}%)</p>
                <p><strong>Skill Match:</strong> ${r.skill_match_pct}%</p>
                <p><strong>ML Prediction:</strong> <span style="color: ${r.ml_prediction === 'Selected' ? 'green' : r.ml_prediction === 'Shortlisted' ? '#17a2b8' : 'red'}; font-weight: bold;">${r.ml_prediction || 'Unknown'}</span> (${r.ml_probability ? (r.ml_probability * 100).toFixed(1) : '0.0'}% Confidence)</p>
                <div style="background:#f8f9fa; padding:10px; border-radius:4px; margin: 10px 0;">
                    <strong>AI Explainer:</strong><br>${r.llm_explanation}
                </div>
                <div>
                    <button class="primary-btn" style="width:auto; margin-top:10px; display:inline-block;" onclick="window.history.pushState(null, '', '/resume-view/${r.resume_id || r._id}'); window.dispatchEvent(new Event('popstate'))">View Highlighted CV</button>
                    ${r.status === 'Selected' ? '' : `<button class="primary-btn" style="width:auto; margin-top:10px; background-color:green; display:inline-block; margin-left:10px;" onclick="window.updateStatus('${r.resume_id || r._id}', 'Selected')">Accept</button>`}
                    ${r.status === 'Shortlisted' ? '' : `<button class="primary-btn" style="width:auto; margin-top:10px; background-color:#17a2b8; display:inline-block; margin-left:10px;" onclick="window.updateStatus('${r.resume_id || r._id}', 'Shortlisted')">Shortlist</button>`}
                    ${r.status === 'Rejected' ? '' : `<button class="primary-btn" style="width:auto; margin-top:10px; background-color:red; display:inline-block; margin-left:10px;" onclick="window.updateStatus('${r.resume_id || r._id}', 'Rejected')">Reject</button>`}
                </div>
            </div>
        `).join("");
    }

    function renderMyApplications() {
        mainContent.innerHTML = `
            <h2>My Applications</h2>
            <div id="my-apps-list" class="job-list">Loading your applications...</div>
        `;
        fetch("/resumes/my-applications", { headers: { "Authorization": `Bearer ${token}` } })
            .then(r => r.json())
            .then(data => {
                const list = document.getElementById("my-apps-list");
                if (data && data.length > 0) {
                    list.innerHTML = data.map(app => `
                        <div class="job-card">
                            <h3>${app.job_title} at ${app.company}</h3>
                            <p>Applied On: ${new Date(app.uploaded_at).toLocaleDateString()}</p>
                            <p>Status: <strong style="color: ${app.status === 'Selected' ? 'green' : app.status === 'Rejected' ? 'red' : app.status === 'Shortlisted' ? '#17a2b8' : '#ffc107'}">${app.status || 'Under Review'}</strong></p>
                        </div>
                    `).join("");
                } else {
                    list.innerHTML = "<p>You haven't applied to any jobs yet.</p>";
                }
            })
            .catch(() => {
                document.getElementById("my-apps-list").innerHTML = "<p>Error loading applications.</p>";
            });
    }

    async function renderJobQuiz(jobId) {
        mainContent.innerHTML = `<p>Loading generated quiz...</p>`;
        try {
            const res = await fetch(`/quiz/${jobId}/view`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                mainContent.innerHTML = `
                    <button class="back-btn" onclick="window.history.pushState(null, '', '/dashboard'); window.dispatchEvent(new Event('popstate'))">← Back to Dashboard</button>
                    <h2>Quiz Generation in Progress</h2>
                    <p style="color: #666; font-size: 1.1em; padding: 20px 0;">⏳ ${data.error || 'Quiz currently generating.'}</p>
                    <p>Google Gemini takes ~5 to 10 seconds to read your job description and write 15 custom questions.</p>
                    <button class="primary-btn" style="width: auto; margin-top: 10px; background-color: #17a2b8;" onclick="loadContent('/job-quiz/${jobId}')">Refresh Page</button>
                `;
                return;
            }
            
            let html = `
                <button class="back-btn" onclick="window.history.pushState(null, '', '/dashboard'); window.dispatchEvent(new Event('popstate'))">← Back to Dashboard</button>
                <h2>Generated Quiz for Job Overview</h2>
                <div style="margin-bottom: 20px;">
                    <p>This is the pre-screening quiz that applicants will see. The system automatically generated it using Gemini based on your job description!</p>
                    <button id="regen-quiz-btn" class="primary-btn" style="background-color: #ffc107; color: #000; width: auto;">Regenerate Quiz via AI</button>
                </div>
            `;
            
            if (data.questions && data.questions.length > 0) {
                html += data.questions.map((q, i) => `
                    <div style="margin-bottom: 15px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #fcfcfc;">
                        <p style="margin-top: 0;"><strong>Q${i+1}: ${q.question}</strong></p>
                        <ul style="list-style-type: none; padding-left: 0; margin-bottom: 0;">
                            ${q.options.map((opt, j) => `
                                <li style="${j === q.correct_index ? 'color: green; font-weight: bold; background-color: #e6ffed; padding: 5px; border-radius: 3px;' : 'padding: 5px;'}">
                                    ${j === q.correct_index ? '✓' : '○'} ${opt}
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                `).join('');
            } else {
                html += `<p>No quiz found or still generating. Try again shortly.</p>`;
            }
            
            mainContent.innerHTML = html;
            
            document.getElementById("regen-quiz-btn").addEventListener("click", async () => {
                if (!confirm("Are you sure you want to completely regenerate the quiz? Existing questions will be replaced.")) return;
                try {
                    const btn = document.getElementById("regen-quiz-btn");
                    btn.disabled = true;
                    btn.textContent = "Regenerating... (Background task started)";
                    
                    const res = await fetch(`/quiz/${jobId}/regenerate`, {
                        method: "POST",
                        headers: { "Authorization": `Bearer ${token}` }
                    });
                    
                    if (res.ok) {
                        alert("Quiz regeneration triggered in the background! Please check back in a few moments to see the new questions.");
                        window.history.pushState(null, '', '/dashboard'); window.dispatchEvent(new Event('popstate'));
                    } else {
                        alert("Failed to regenerate.");
                        btn.disabled = false;
                        btn.textContent = "Regenerate Quiz via AI";
                    }
                } catch(e) { alert("Error connecting to server."); }
            });

        } catch(e) {
            mainContent.innerHTML = `<p>Error loading quiz.</p>`;
        }
    }



    async function renderResumeView(resumeId) {
        mainContent.innerHTML = `<p>Loading Resume data...</p>`;

        try {
            const res = await fetch(`/resumes/detail/${resumeId}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Resume not found or unauthorized");
            const data = await res.json();

            let highlightedText = data.raw_text || "No text available.";

            // Highlight BERT sentences FIRST (since they are longer strings)
            if (data.bert_matched_sentences && data.bert_matched_sentences.length) {
                data.bert_matched_sentences.forEach(sentence => {
                    // It can be difficult to escape arbitrary strings for exact regex matching,
                    // so we do our best to escape control chars.
                    const safeSentence = sentence.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(safeSentence, 'gi');
                    highlightedText = highlightedText.replace(regex, `<span style="background-color: #fef08a; padding: 0 4px; border-radius: 3px; display: inline-block; margin: 2px 0;">$&</span>`); // Light yellow
                });
            }

            // Highlight explicit skills SECOND
            if (data.matched_skills && data.matched_skills.length) {
                // Sort skills by length descending
                const sortedSkills = [...data.matched_skills].sort((a, b) => b.length - a.length);
                sortedSkills.forEach(skill => {
                    // Safe basic replacement. Nesting spans is perfectly valid HTML.
                    const regex = new RegExp(`\\b${skill}\\b`, 'gi');
                    highlightedText = highlightedText.replace(regex, `<span style="background-color: #a7f3d0; padding: 0 4px; border-radius: 3px; font-weight: bold;">$&</span>`); // Light green
                });
            }

            mainContent.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <button class="back-btn" onclick="window.history.back()">← Back</button>
                </div>
                <h2>Resume: ${data.candidate_name}</h2>
                <div style="display:flex; gap: 20px;">
                    <div style="flex:2; background:#fff; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); white-space:pre-wrap; font-family: monospace; line-height:1.5;">${highlightedText}</div>
                    <div style="flex:1;">
                        <div class="job-card" style="margin-bottom:20px;">
                            <h3>Score Summary</h3>
                            <p><strong>Hybrid:</strong> ${data.hybrid_score}%</p>
                            <p><strong>Quiz:</strong> ${data.quiz_score}%</p>
                            <p><strong>TF-IDF:</strong> ${data.tfidf_score}%</p>
                            <p><strong>BERT:</strong> ${data.bert_score}%</p>
                            <p><strong>Skill Match:</strong> ${data.skill_match_pct}%</p>
                            <hr style="margin: 10px 0; border: 0; border-top: 1px solid #ddd;">
                            <p><strong>ML Prediction:</strong> <span style="color: ${data.ml_prediction === 'Selected' ? 'green' : data.ml_prediction === 'Shortlisted' ? '#17a2b8' : 'red'}; font-weight: bold;">${data.ml_prediction || 'Unknown'}</span></p>
                            <p><strong>ML Confidence:</strong> ${data.ml_probability ? (data.ml_probability * 100).toFixed(1) : '0.0'}%</p>
                        </div>
                        <div class="job-card" style="margin-bottom:20px;">
                            <h3>Key Findings</h3>
                            <p><strong>Matches:</strong> ${data.matched_skills.join(", ") || "None"}</p>
                            <p><strong>Missing:</strong> ${data.missing_skills.join(", ") || "None"}</p>
                        </div>
                        <div class="job-card" style="background-color: #f1f8ff;">
                            <h3>AI Explainer</h3>
                            <p style="font-size: 0.9em;">${data.llm_explanation}</p>
                        </div>
                    </div>
                </div>
            `;

        } catch (err) {
            mainContent.innerHTML = `<p>Error loading resume details.</p>`;
        }
    }

    // Handle initial client routing
    window.addEventListener("popstate", () => loadContent(window.location.pathname));
    document.body.addEventListener("click", e => {
        if (e.target.matches("[data-link]")) {
            e.preventDefault();
            history.pushState(null, null, e.target.getAttribute("href"));
            loadContent(window.location.pathname);
        }
    });

    const redirectIntent = localStorage.getItem("redirect_after_login");
    if (redirectIntent && token) {
        localStorage.removeItem("redirect_after_login");
        history.pushState(null, null, redirectIntent);
        loadContent(redirectIntent);
    } else {
        loadContent(window.location.pathname);
    }
});
