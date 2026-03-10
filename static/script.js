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

                const tr = document.createElement("tr");
                tr.innerHTML = `
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
});
