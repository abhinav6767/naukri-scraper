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
    const btnPauseApply = document.getElementById("btn-pause-apply");
    const selectAllJobs = document.getElementById("select-all-jobs");
    const selectAllQJobs = document.getElementById("select-all-q-jobs");
    const selectAllCJobs = document.getElementById("select-all-c-jobs");
    const btnApplyQuestionnaire = document.getElementById("btn-apply-questionnaire");
    const btnApplyCompany = document.getElementById("btn-apply-company");
    const qTableBody = document.getElementById("questionnaire-body");
    const cTableBody = document.getElementById("company-site-body");
    const qContainer = document.getElementById("questionnaire-jobs-container");
    const cContainer = document.getElementById("company-site-jobs-container");
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
            window.allScrapedJobs = jobs;

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
                    ? `<i data-lucide="check-circle-2" style="color:var(--accent-green); width: 20px; height: 20px;" title="Already Applied"></i>`
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

            const tablesLayout = document.getElementById("tables-layout");
            if (tablesLayout) tablesLayout.classList.remove("hidden");
            tableContainer.classList.remove("hidden");
            if (btnStartApply) btnStartApply.classList.remove("hidden");
            currentContextFilename = filename;

            // Add a small delay to let the DOM paint, then smooth scroll down
            setTimeout(() => {
                lucide.createIcons();
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
        btnText.innerHTML = `<div class="loader"></div> Scraping...`;
        loader.classList.add("hidden");

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
                btnText.innerHTML = `<i data-lucide="play" style="width: 20px; height: 20px;"></i> Start Scraping`;
                lucide.createIcons();
                loader.classList.add("hidden");
            });

        } catch (error) {
            appendLog(`Error: ${error.message}`, "error");
            startBtn.disabled = false;
            btnText.innerHTML = `<i data-lucide="play" style="width: 20px; height: 20px;"></i> Start Scraping`;
            lucide.createIcons();
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
            document.querySelectorAll(".job-checkbox").forEach(cb => cb.checked = e.target.checked);
        });
    }

    if (selectAllQJobs) {
        selectAllQJobs.addEventListener("change", (e) => {
            document.querySelectorAll(".q-job-checkbox").forEach(cb => cb.checked = e.target.checked);
        });
    }

    if (selectAllCJobs) {
        selectAllCJobs.addEventListener("change", (e) => {
            document.querySelectorAll(".c-job-checkbox").forEach(cb => cb.checked = e.target.checked);
        });
    }
    
    function handleJobStatusUpdate(data) {
        // Depending on status, log it and move the row.
        appendLog(`[RESULT] ${data.companyName} - ${data.title}: ${data.status}`);
        
        // Find existing row in the main table
        const cb = document.querySelector(`#table-body input[value="${data.jobId}"]`);
        const mainRow = cb ? cb.closest('tr') : null;
        
        if (data.status === "Questionnaire Detected") {
            if (mainRow) mainRow.remove();
            
            qContainer.classList.remove("hidden");
            
            // find snippet from global array
            const job = window.allScrapedJobs?.find(j => j.jobId === data.jobId) || {};
            const snippet = (job.shortDescription || job.jobDescription || "").replace(/<[^>]+>/g, '').substring(0, 100) + '...';
            
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="text-align:center"><input type="checkbox" class="q-job-checkbox" value="${data.jobId}"></td>
                <td><strong><a href="${data.jdURL || '#'}" target="_blank" style="color:var(--accent-blue); text-decoration:none;">${data.title}</a></strong></td>
                <td>${data.companyName}</td>
                <td style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${snippet}">${snippet}</td>
            `;
            qTableBody.appendChild(tr);
            lucide.createIcons();
            
        } else if (data.status.includes("Company Site")) {
            if (mainRow) mainRow.remove();
            
            cContainer.classList.remove("hidden");
            
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="text-align:center"><input type="checkbox" class="c-job-checkbox" value="${data.jdURL}"></td>
                <td><strong>${data.title}</strong></td>
                <td>${data.companyName}</td>
                <td><a href="${data.jdURL}" target="_blank" class="btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.8rem; text-decoration: none; display: inline-block;"><i data-lucide="external-link" style="width: 14px; height: 14px; margin-right: 4px; vertical-align: text-bottom;"></i> Open Link</a></td>
            `;
            cTableBody.appendChild(tr);
            lucide.createIcons();
            
        } else if (data.status.includes("Success") || data.status === "Already Applied") {
            if (mainRow) {
                // Update checkbox to green tick
                const td = mainRow.querySelector("td:first-child");
                if (td) {
                    td.innerHTML = `<i data-lucide="check-circle-2" style="color:var(--accent-green); width: 20px; height: 20px;" title="${data.status}"></i>`;
                    lucide.createIcons();
                }
                mainRow.style.opacity = "0.6";
            }
        }
    }
    
    function attachApplyLogic(button, checkboxClass, isQuestionnaire = false) {
        button.addEventListener("click", async () => {
            const checkboxes = document.querySelectorAll(`.${checkboxClass}:checked`);
            const jobIds = Array.from(checkboxes).map(cb => cb.value);

            if (jobIds.length === 0) {
                alert("Please select at least one job to apply to.");
                return;
            }

            appendLog(`Starting application process for ${jobIds.length} jobs...`, "info");
            button.disabled = true;
            const originalText = button.innerHTML;
            button.innerHTML = `<i data-lucide="loader-2" class="lucide-spin" style="width: 16px; height: 16px;"></i> Applying...`;
            lucide.createIcons();
            if (btnPauseApply) btnPauseApply.classList.remove("hidden");

            try {
                const res = await fetch("/api/start_apply", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        job_ids: jobIds,
                        context_filename: currentContextFilename,
                        is_questionnaire_run: isQuestionnaire
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
                        button.innerHTML = `<i data-lucide="pause-circle" style="width: 16px; height: 16px;"></i> Paused (Questionnaire)`;
                        lucide.createIcons();
                        if (btnPauseApply) btnPauseApply.classList.add("hidden");
                        if (btnResumeApply) btnResumeApply.classList.remove("hidden");
                        
                        const audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
                        audio.play().catch(e => console.log("Audio play failed:", e));
                        
                        setTimeout(() => {
                            if (confirm("Questionnaire paused. Press OK AFTER you have completed the questionnaire in Edge to resume applying.")) {
                                if (btnResumeApply && !btnResumeApply.classList.contains("hidden")) {
                                    btnResumeApply.click();
                                }
                            }
                        }, 500);
                    } else if (msg === "===USER_PAUSED===") {
                        appendLog("Bot paused. Click Resume when ready to continue applying.", "warn");
                        button.innerHTML = `<i data-lucide="pause-circle" style="width: 16px; height: 16px;"></i> Paused (User)`;
                        lucide.createIcons();
                        if (btnPauseApply) btnPauseApply.classList.add("hidden");
                        if (btnResumeApply) btnResumeApply.classList.remove("hidden");
                    } else if (msg.startsWith("|||") && msg.endsWith("|||")) {
                        try {
                            const parsedData = JSON.parse(msg.substring(3, msg.length - 3));
                            handleJobStatusUpdate(parsedData);
                            
                            // If it's the questionnaire table and it resulted in success, update row in qTable
                            if (isQuestionnaire && (parsedData.status.includes("Success") || parsedData.status === "Already Applied")) {
                                const qCb = document.querySelector(`#questionnaire-body input[value="${parsedData.jobId}"]`);
                                const qRow = qCb ? qCb.closest('tr') : null;
                                if (qRow) {
                                    const td = qRow.querySelector("td:first-child");
                                    if (td) {
                                        td.innerHTML = `<i data-lucide="check-circle-2" style="color:var(--accent-green); width: 20px; height: 20px;" title="${parsedData.status}"></i>`;
                                        lucide.createIcons();
                                    }
                                    qRow.style.opacity = "0.6";
                                }
                            }
                        } catch(e) {
                            console.error("Failed parsing UI message:", e);
                        }
                    } else {
                        appendLog(msg);
                    }
                };
                
                eventSource.addEventListener("end", async (event) => {
                    eventSource.close();
                    appendLog("Application run finished.", "success");
                    button.disabled = false;
                    button.innerHTML = originalText;
                    if (btnResumeApply) btnResumeApply.classList.add("hidden");
                    if (btnPauseApply) btnPauseApply.classList.add("hidden");

                    if (currentContextFilename) {
                        appendLog("Refreshing table to show new applied statuses...", "info");
                        // We do not re-render the whole table here so row shifts aren't lost immediately,
                        // unless we specifically want a fresh start. We're keeping DOM updates manual.
                    }
                });
            } catch (error) {
                appendLog(`Error starting apply: ${error.message}`, "error");
                button.disabled = false;
                button.innerHTML = originalText;
                if (btnPauseApply) btnPauseApply.classList.add("hidden");
            }
        });
    }

    if (btnStartApply) {
        attachApplyLogic(btnStartApply, "job-checkbox", false);
    }
    
    if (btnApplyQuestionnaire) {
        attachApplyLogic(btnApplyQuestionnaire, "q-job-checkbox", true);
    }

    if (btnApplyCompany) {
        btnApplyCompany.addEventListener("click", () => {
            const checkboxes = document.querySelectorAll(".c-job-checkbox:checked");
            const urls = Array.from(checkboxes).map(cb => cb.value);
            if (urls.length === 0) {
                alert("Please select at least one company site job.");
                return;
            }
            urls.forEach(url => window.open(url, "_blank"));
            appendLog(`Opened ${urls.length} company links in new tabs.`, "info");
        });
    }

    if (btnPauseApply) {
        btnPauseApply.addEventListener("click", async () => {
            if (!currentApplyTaskId) return;
            appendLog("Requesting pause after current job...", "info");
            try {
                const res = await fetch(`/api/pause_apply/${currentApplyTaskId}`, { method: "POST" });
                if (!res.ok) throw new Error("Failed to request pause");
            } catch (err) {
                appendLog("Error pausing: " + err.message, "error");
            }
        });
    }

    if (btnResumeApply) {
        btnResumeApply.addEventListener("click", async () => {
            if (!currentApplyTaskId) return;

            appendLog("Sending resume signal...", "info");
            btnResumeApply.classList.add("hidden");
            if (btnPauseApply) btnPauseApply.classList.remove("hidden");
            btnStartApply.innerHTML = `<i data-lucide="loader-2" class="lucide-spin" style="width: 16px; height: 16px;"></i> Applying...`;
            if (btnApplyQuestionnaire) btnApplyQuestionnaire.innerHTML = `<i data-lucide="loader-2" class="lucide-spin" style="width: 16px; height: 16px;"></i> Apply to Selected`;
            lucide.createIcons();

            try {
                const res = await fetch(`/api/resume_apply/${currentApplyTaskId}`, { method: "POST" });
                if (!res.ok) throw new Error("Failed to resume task");
            } catch (err) {
                appendLog("Error resuming: " + err.message, "error");
                btnResumeApply.classList.remove("hidden");
                if (btnPauseApply) btnPauseApply.classList.add("hidden");
            }
        });
    }
});
