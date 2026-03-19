document.addEventListener("DOMContentLoaded", () => {

    // ── DUAL EXPERIENCE SLIDER ──────────────────────────────────────────────
    const expMin = document.getElementById("exp-min");
    const expMax = document.getElementById("exp-max");
    const expMinLabel = document.getElementById("exp-min-label");
    const expMaxLabel = document.getElementById("exp-max-label");
    const rangeFill  = document.getElementById("range-fill");

    function updateSlider() {
        if (!expMin || !expMax) return;
        let lo = parseInt(expMin.value);
        let hi = parseInt(expMax.value);
        // Prevent thumbs from crossing
        if (lo > hi) { lo = hi; expMin.value = lo; }
        if (hi < lo) { hi = lo; expMax.value = hi; }
        const max = parseInt(expMin.max);
        const pctLo = (lo / max) * 100;
        const pctHi = (hi / max) * 100;
        if (rangeFill)  { rangeFill.style.left = pctLo + "%"; rangeFill.style.width = (pctHi - pctLo) + "%"; }
        if (expMinLabel) expMinLabel.innerHTML = `Min: <strong>${lo}</strong> yrs`;
        if (expMaxLabel) expMaxLabel.innerHTML = `Max: <strong>${hi}</strong> yrs`;
    }

    if (expMin) expMin.addEventListener("input", updateSlider);
    if (expMax) expMax.addEventListener("input", updateSlider);
    updateSlider(); // set initial state
    // ────────────────────────────────────────────────────────────────────────

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
            if (btnStartApply) btnStartApply.classList.remove("hidden");
            currentContextFilename = filename;

            // Hide live results empty state if we have rows
            const liveEmpty = document.getElementById("live-empty-state");
            if (liveEmpty) liveEmpty.style.display = jobs.length > 0 ? "none" : "flex";

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
        logWindow.innerHTML = "";
        appendLog("Initializing scraper...", "info");

        // Show all 3 table panels right away (they will show empty states)
        const tablesLayout = document.getElementById("tables-layout");
        if (tablesLayout) tablesLayout.classList.remove("hidden");
        // Reset bodies
        document.getElementById("table-body").innerHTML = "";
        document.getElementById("questionnaire-body").innerHTML = "";
        document.getElementById("company-site-body").innerHTML = "";
        // Show empty states
        const liveEmpty = document.getElementById("live-empty-state");
        const qEmpty = document.getElementById("q-empty-state");
        const cEmpty = document.getElementById("c-empty-state");
        if (liveEmpty) liveEmpty.style.display = "flex";
        if (qEmpty) qEmpty.style.display = "flex";
        if (cEmpty) cEmpty.style.display = "flex";

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

    function updateCostAndCheckLimits() {
        const regularChecked = document.querySelectorAll(".job-checkbox:checked").length;
        // const qChecked = document.querySelectorAll(".q-job-checkbox:checked").length; // If you want to limit Q jobs. Usually they use same apply button logic.
        const totalChecked = regularChecked; // Just limiting the main ones for now, easy to extend
        
        const costLabel = document.getElementById("apply-cost");
        const qtyLabel = document.getElementById("apply-btn-qty");
        const userCreds = window.USER_CREDITS || 0;
        
        if (costLabel) costLabel.innerHTML = `Cost: ${totalChecked} / ${userCreds} Credits`;
        if (qtyLabel) qtyLabel.innerText = totalChecked;
    }

    // Delegate checkbox changes for limits
    document.addEventListener("change", (e) => {
        if (e.target.classList.contains("job-checkbox") || e.target.id === "select-all-jobs") {
            // Count after change
            const totalChecked = document.querySelectorAll(".job-checkbox:checked").length;
            const userCreds = window.USER_CREDITS || 0;
            
            if (totalChecked > userCreds) {
                alert(`You only have ${userCreds} credits available. You cannot select more jobs.`);
                e.target.checked = false;
                
                // If it was select-all, uncheck the ones that put us over limit
                if (e.target.id === "select-all-jobs") {
                    let count = 0;
                    document.querySelectorAll(".job-checkbox").forEach(cb => {
                        if (count >= userCreds) cb.checked = false;
                        else if (cb.checked) count++;
                    });
                }
            }
            updateCostAndCheckLimits();
        }
    });

    if (selectAllJobs) {
        selectAllJobs.addEventListener("change", (e) => {
            const userCreds = window.USER_CREDITS || 0;
            let count = 0;
            document.querySelectorAll(".job-checkbox").forEach(cb => {
                if (e.target.checked) {
                    if (count < userCreds) {
                        cb.checked = true;
                        count++;
                    } else {
                        cb.checked = false;
                    }
                } else {
                    cb.checked = false;
                }
            });
            updateCostAndCheckLimits();
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
    
    window.sessionAppliedJobs = window.sessionAppliedJobs || [];

    function handleJobStatusUpdate(data) {
        // Depending on status, log it and move the row.
        appendLog(`[RESULT] ${data.companyName} - ${data.title}: ${data.status}`);
        
        // Find existing row in the main table
        const cb = document.querySelector(`#table-body input[value="${data.jobId}"]`);
        const mainRow = cb ? cb.closest('tr') : null;
        
        if (data.status === "Questionnaire Detected") {
            if (mainRow) mainRow.remove();
            
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
            // hide empty state
            const qEmpty = document.getElementById("q-empty-state");
            if (qEmpty) qEmpty.style.display = "none";
            lucide.createIcons();
            
        } else if (data.status.includes("Company Site")) {
            if (mainRow) mainRow.remove();
            
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="text-align:center"><input type="checkbox" class="c-job-checkbox" value="${data.jdURL}"></td>
                <td><strong>${data.title}</strong></td>
                <td>${data.companyName}</td>
                <td><a href="${data.jdURL}" target="_blank" class="btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.8rem; text-decoration: none; display: inline-block;"><i data-lucide="external-link" style="width: 14px; height: 14px; margin-right: 4px; vertical-align: text-bottom;"></i> Open Link</a></td>
            `;
            cTableBody.appendChild(tr);
            // hide empty state
            const cEmpty = document.getElementById("c-empty-state");
            if (cEmpty) cEmpty.style.display = "none";
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
            
            // Push to session jobs for API recording
            if (data.status.includes("Success")) {
                
                // --- -1 Credit Floating Animation ---
                const anim = document.createElement("div");
                anim.innerHTML = "-1 Credit";
                anim.style.position = "fixed";
                anim.style.top = "50%";
                anim.style.left = "50%";
                anim.style.transform = "translate(-50%, -50%)";
                anim.style.color = "#ef4444"; // Red
                anim.style.fontWeight = "bold";
                anim.style.fontSize = "3.5rem";
                anim.style.zIndex = "99999";
                anim.style.pointerEvents = "none";
                anim.style.textShadow = "0 0 20px rgba(239, 68, 68, 0.6)";
                anim.style.animation = "float-up-fade 2s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards";
                document.body.appendChild(anim);
                
                if (!document.getElementById("credit-anim-style")) {
                    const style = document.createElement("style");
                    style.id = "credit-anim-style";
                    style.textContent = `
                        @keyframes float-up-fade {
                            0% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
                            15% { opacity: 1; transform: translate(-50%, -60%) scale(1.1); }
                            30% { opacity: 1; transform: translate(-50%, -60%) scale(1); }
                            100% { opacity: 0; transform: translate(-50%, -150%) scale(0.9); }
                        }
                    `;
                    document.head.appendChild(style);
                }
                setTimeout(() => anim.remove(), 2000);
                // ------------------------------------
                
                const jobFromMem = window.allScrapedJobs?.find(j => j.jobId === data.jobId);
                if (jobFromMem && !window.sessionAppliedJobs.find(x => x.jobId === data.jobId)) {
                    window.sessionAppliedJobs.push(jobFromMem);
                }
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
                // First open Edge automatically
                appendLog("Connecting to Microsoft Edge...", "info");
                try {
                    await fetch("/api/open_edge", { method: "POST" });
                } catch (edgeErr) {
                    appendLog("Failed to auto-open edge: " + edgeErr.message, "warn");
                }
                const res = await fetch("/api/start_apply", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        job_ids: jobIds,
                        context_filename: currentContextFilename,
                        is_questionnaire_run: isQuestionnaire,
                        userId: window.USER_ID || ""
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
                        
                    } else if (msg === "===USER_PAUSED===") {
                        appendLog("Bot paused. Click Resume when ready to continue applying.", "warn");
                        button.innerHTML = `<i data-lucide="pause-circle" style="width: 16px; height: 16px;"></i> Paused (User)`;
                        lucide.createIcons();
                        if (btnPauseApply) btnPauseApply.classList.add("hidden");
                        if (btnResumeApply) btnResumeApply.classList.remove("hidden");
                    } else if (msg.startsWith("|||") && msg.endsWith("|||")) {
                try {
                    const parsedData = JSON.parse(msg.substring(3, msg.length - 3));
                    // Fix relative URLs if Naukri returned them without the domain
                    if (parsedData.jdURL && !parsedData.jdURL.startsWith("http")) {
                        parsedData.jdURL = "https://www.naukri.com" + parsedData.jdURL;
                    }
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
                                    qRow.style.animation = "none";
                                }
                            } else if (!isQuestionnaire && parsedData.status === "Questionnaire Detected") {
                                // Add highlight animation to the newly injected questionnaire row natively!
                                setTimeout(() => {
                                    const rawCb = document.querySelector(`#questionnaire-body input[value="${parsedData.jobId}"]`);
                                    if (rawCb && rawCb.closest('tr')) {
                                        const newQRow = rawCb.closest('tr');
                                        newQRow.style.animation = "pulse-glow 2s infinite";
                                        
                                        if(!document.getElementById("pulse-glow-style")) {
                                            const gStyle = document.createElement("style");
                                            gStyle.id = "pulse-glow-style";
                                            gStyle.innerHTML = "@keyframes pulse-glow { 0% { box-shadow: 0 0 0px var(--accent-yellow); } 50% { box-shadow: inset 0 0 15px var(--accent-yellow); background: rgba(234, 179, 8, 0.1); } 100% { box-shadow: 0 0 0px var(--accent-yellow); } }";
                                            document.head.appendChild(gStyle);
                                        }
                                    }
                                }, 500);
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

                    if (window.sessionAppliedJobs && window.sessionAppliedJobs.length > 0) {
                        try {
                            const count = window.sessionAppliedJobs.length;
                            await fetch("http://localhost:3000/api/record-applications", {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ userId: window.USER_ID, appliedJobs: window.sessionAppliedJobs })
                            });
                            
                            // Show congratulatory popup
                            const overlay = document.createElement("div");
                            overlay.style.position = "fixed";
                            overlay.style.top = "0"; overlay.style.left = "0";
                            overlay.style.width = "100%"; overlay.style.height = "100%";
                            overlay.style.background = "rgba(0,0,0,0.85)";
                            overlay.style.display = "flex";
                            overlay.style.alignItems = "center"; overlay.style.justifyContent = "center";
                            overlay.style.zIndex = "9999";
                            
                            const popup = document.createElement("div");
                            popup.style.background = "#18181b"; // zinc-900
                            popup.style.padding = "2.5rem";
                            popup.style.borderRadius = "16px";
                            popup.style.textAlign = "center";
                            popup.style.border = "1px solid var(--accent-green)";
                            popup.style.boxShadow = "0 20px 40px rgba(16, 185, 129, 0.2)";
                            popup.style.maxWidth = "400px";
                            
                            popup.innerHTML = `
                                <i data-lucide="party-popper" style="width: 56px; height: 56px; color: var(--accent-green); margin: 0 auto 1rem;"></i>
                                <h2 style="color: white; margin-bottom: 0.5rem; font-size: 1.5rem;">Job Hunt Success!</h2>
                                <p style="color: var(--text-muted); margin-bottom: 1.5rem; line-height: 1.5;">You successfully applied to <strong style="color: white; font-size: 1.2rem;">${count}</strong> jobs organically. They have been added to your primary dashboard!</p>
                                <button class="btn-primary" style="width: 100%;" onclick="this.parentElement.parentElement.remove()">Keep Going</button>
                            `;
                            
                            overlay.appendChild(popup);
                            document.body.appendChild(overlay);
                            lucide.createIcons();
                            
                            window.sessionAppliedJobs = [];
                        } catch(e) {
                            appendLog("Failed to record applications to database: " + e.message, "error");
                        }
                    }

                    if (currentContextFilename) {
                        appendLog("Finished processing current batch.", "info");
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
