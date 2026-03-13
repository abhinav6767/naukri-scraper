document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("scrape-form");
    const startBtn = document.getElementById("start-btn");
    const loader = document.querySelector(".loader");
    const btnText = document.querySelector(".btn-text");
    const logWindow = document.getElementById("log-window");
    const downloadPanel = document.getElementById("download-panel");
    const btnJson = document.getElementById("btn-download-json");
    const btnCsv = document.getElementById("btn-download-csv");
    const tableContainer = document.getElementById("results-table-container");
    const tableBody = document.getElementById("table-body");

    const btnOpenEdge = document.getElementById("btn-open-edge");
    const btnStartApply = document.getElementById("btn-start-apply");
    const btnResumeApply = document.getElementById("btn-resume-apply");
    const selectAllJobs = document.getElementById("select-all-jobs");
    let currentContextFilename = "";
    let currentApplyTaskId = null;

    const jobTypeSelect = document.getElementById("job_type");
    const internshipFilters = document.getElementById("internship-filters");

    if (jobTypeSelect && internshipFilters) {
        jobTypeSelect.addEventListener("change", (e) => {
            if (e.target.value === "internship") {
                internshipFilters.classList.remove("hidden");
            } else {
                internshipFilters.classList.add("hidden");
            }
        });
    }

    let eventSource = null;

    function appendLog(message, type = "") {
        const line = document.createElement("div");
        line.className = `log-line ${type}`;
        line.textContent = message;
        logWindow.appendChild(line);
        logWindow.scrollTop = logWindow.scrollHeight; // Auto-scroll
    }

    async function renderResultsTable(filename) {
        try {
            // First fetch the list of applied jobs
            let appliedJobs = [];
            try {
                const appliedRes = await fetch('/api/applied_jobs');
                if (appliedRes.ok) {
                    appliedJobs = await appliedRes.json();
                }
            } catch (e) {
                console.warn("Could not fetch applied jobs list");
            }

            const res = await fetch(`/api/download/${filename}`);
            if (!res.ok) throw new Error("Could not fetch JSON for table display");
            const jobs = await res.json();

            tableBody.innerHTML = "";

            // Sort jobs by CV Match Score (highest first)
            jobs.sort((a, b) => {
                const scoreA = a.cvMatchScore || 0;
                const scoreB = b.cvMatchScore || 0;
                return scoreB - scoreA;
            });

            jobs.forEach(job => {
                let matchHtml = `<span style="color:var(--text-muted)">N/A</span>`;
                if (job.cvMatchScore !== undefined && job.cvMatchScore !== null) {
                    let badgeClass = "match-low";
                    if (job.cvMatchScore >= 65) badgeClass = "match-high";
                    else if (job.cvMatchScore >= 35) badgeClass = "match-med";
                    matchHtml = `<span class="match-badge ${badgeClass}">${job.cvMatchScore}%</span>`;
                }

                // Get work mode text
                let workMode = job.workMode || job.wfhLabel || "";
                if (!workMode && job.tagsAndSkills) {
                    if (job.tagsAndSkills.toLowerCase().includes("remote")) workMode = "Remote";
                    else if (job.tagsAndSkills.toLowerCase().includes("hybrid")) workMode = "Hybrid";
                }

                // Get short snippet
                let snippet = (job.shortDescription || job.jobDescription || "").replace(/<[^>]+>/g, '');

                const isApplied = appliedJobs.includes(job.jobId);
                const checkboxHtml = isApplied
                    ? `<span style="color:var(--accent-green); font-size: 1.2rem;" title="Already Applied">✅</span>`
                    : `<input type="checkbox" class="job-checkbox" value="${job.jobId}">`;

                const tr = document.createElement("tr");
                if (isApplied) tr.style.opacity = "0.6"; // Dim applied rows

                tr.innerHTML = `
                    <td style="text-align:center">${checkboxHtml}</td>
                    <td>${matchHtml}</td>
                    <td><strong><a href="${job.jdURL || '#'}" target="_blank" style="color:var(--accent-blue); text-decoration:none;">${job.title || "Unknown"}</a></strong></td>
                    <td>${job.companyName || ""}</td>
                    <td>${job.experience || ""}</td>
                    <td>${job.salary || "Not Disclosed"}</td>
                    <td>${workMode}</td>
                    <td style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${snippet}">${snippet}</td>
                `;
                tableBody.appendChild(tr);
            });

            tableContainer.classList.remove("hidden");
            if (btnStartApply) btnStartApply.classList.remove("hidden");
            currentContextFilename = filename;

            // Add a small delay to let the DOM paint, then smooth scroll down
            setTimeout(() => {
                tableContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);

        } catch (err) {
            appendLog(`Table Render Error: ${err.message}`, "warn");
        }
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // 1. Reset UI State
        downloadPanel.classList.add("hidden");
        tableContainer.classList.add("hidden");
        logWindow.innerHTML = "";
        appendLog("Initializing scraper...", "info");

        startBtn.disabled = true;
        btnText.textContent = "Scraping...";
        loader.classList.remove("hidden");

        // 2. Prepare Form Data
        const formData = new FormData(form);

        try {
            // 3. Start the scrape task on backend
            const response = await fetch("/api/scrape", {
                method: "POST",
                body: formData
            });

            if (!response.ok) throw new Error("Failed to start scrape");
            const data = await response.json();
            const taskId = data.task_id;

            appendLog(`Task assigned ID: ${taskId}`, "info");

            // 4. Connect to Server-Sent Events for Live Logs
            if (eventSource) {
                eventSource.close();
            }

            eventSource = new EventSource(`/api/logs/${taskId}`);

            eventSource.onmessage = (event) => {
                const msg = event.data;
                appendLog(msg);
            };

            eventSource.onerror = (error) => {
                console.error("SSE Error:", error);
            };

            // Custom event for when stream ends from backend
            eventSource.addEventListener("end", async (event) => {
                eventSource.close();
                appendLog("Stream finished. Processing output...", "success");

                // 5. Check final status to get download links
                const statusRes = await fetch(`/api/status/${taskId}`);
                const statusData = await statusRes.json();

                if (statusData.status === "completed" && statusData.files) {
                    if (statusData.files.json) {
                        btnJson.href = `/api/download/${statusData.files.json}`;
                        // Render the UI table automatically
                        await renderResultsTable(statusData.files.json);
                    }
                    if (statusData.files.csv) {
                        btnCsv.href = `/api/download/${statusData.files.csv}`;
                    }
                    downloadPanel.classList.remove("hidden");
                } else if (statusData.status === "error") {
                    appendLog("Task finished with errors. The API constraints may be too strict or the network was blocked.", "error");
                }

                // Restore UI
                startBtn.disabled = false;
                btnText.textContent = "Start Scraping";
                loader.classList.add("hidden");
            });

        } catch (error) {
            appendLog(`Error: ${error.message}`, "error");
            startBtn.disabled = false;
            btnText.textContent = "Start Scraping";
            loader.classList.add("hidden");
        }
    });

    if (btnOpenEdge) {
        btnOpenEdge.addEventListener("click", async () => {
            try {
                appendLog("Launching Microsoft Edge with debugging...", "info");
                const res = await fetch("/api/open_edge", { method: "POST" });
                const data = await res.json();
                if (data.status === "success") {
                    appendLog("Edge launched successfully. Ready to connect and apply.", "success");
                } else {
                    appendLog("Failed to launch Edge: " + data.error, "error");
                }
            } catch (err) {
                appendLog("Error launching Edge: " + err.message, "error");
            }
        });
    }

    if (selectAllJobs) {
        selectAllJobs.addEventListener("change", (e) => {
            const checkboxes = document.querySelectorAll(".job-checkbox");
            checkboxes.forEach(cb => cb.checked = e.target.checked);
        });
    }

    if (btnStartApply) {
        btnStartApply.addEventListener("click", async () => {
            const checkboxes = document.querySelectorAll(".job-checkbox:checked");
            const jobIds = Array.from(checkboxes).map(cb => cb.value);

            if (jobIds.length === 0) {
                alert("Please select at least one job to apply to.");
                return;
            }

            appendLog(`Starting application process for ${jobIds.length} jobs...`, "info");
            btnStartApply.disabled = true;
            btnStartApply.innerHTML = "🚀 Applying...";

            try {
                const res = await fetch("/api/start_apply", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        job_ids: jobIds,
                        context_filename: currentContextFilename
                    })
                });

                if (!res.ok) throw new Error("Failed to start applying");
                const data = await res.json();
                const taskId = data.task_id;
                currentApplyTaskId = taskId;

                if (eventSource) {
                    eventSource.close();
                }

                eventSource = new EventSource(`/api/logs/${taskId}`);
                eventSource.onmessage = (event) => {
                    const msg = event.data;
                    if (msg === "===PAUSED===") {
                        appendLog("Waiting for you to complete questionnaire... click Resume when done.", "warn");
                        btnStartApply.innerHTML = "⏸️ Paused (Questionnaire)";
                        if (btnResumeApply) btnResumeApply.classList.remove("hidden");
                    } else {
                        appendLog(msg);
                    }
                };
                eventSource.addEventListener("end", async (event) => {
                    eventSource.close();
                    appendLog("Application run finished.", "success");
                    btnStartApply.disabled = false;
                    btnStartApply.innerHTML = "🚀 Start Applying";
                    if (btnResumeApply) btnResumeApply.classList.add("hidden");

                    // Refresh table to show newly applied badges
                    if (currentContextFilename) {
                        appendLog("Refreshing table to show new applied statuses...", "info");
                        await renderResultsTable(currentContextFilename);
                    }
                });
            } catch (error) {
                appendLog(`Error starting apply: ${error.message}`, "error");
                btnStartApply.disabled = false;
                btnStartApply.innerHTML = "🚀 Start Applying";
            }
        });
    }

    if (btnResumeApply) {
        btnResumeApply.addEventListener("click", async () => {
            if (!currentApplyTaskId) return;

            appendLog("Sending resume signal...", "info");
            btnResumeApply.classList.add("hidden");
            btnStartApply.innerHTML = "🚀 Applying...";

            try {
                const res = await fetch(`/api/resume_apply/${currentApplyTaskId}`, { method: "POST" });
                if (!res.ok) throw new Error("Failed to resume task");
            } catch (err) {
                appendLog("Error resuming: " + err.message, "error");
                btnResumeApply.classList.remove("hidden");
                btnStartApply.innerHTML = "⏸️ Paused (Questionnaire)";
            }
        });
    }
});
