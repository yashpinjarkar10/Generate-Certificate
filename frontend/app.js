// Bulk Certificate Generator Frontend Logic
document.addEventListener("DOMContentLoaded", () => {
  // --- Elements ---
  const apiUrlInput = document.getElementById("api-url");
  const btnCheckHealth = document.getElementById("btn-check-health");
  const btnDocsLink = document.getElementById("btn-docs-link");
  const statusBadge = document.getElementById("system-status-badge");
  const statusDot = document.getElementById("status-dot");
  const healthText = document.getElementById("health-text");

  // Tabs
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Form Tab
  const interactiveForm = document.getElementById("interactive-form");
  const recipientRows = document.getElementById("recipient-rows");
  const btnAddRow = document.getElementById("btn-add-row");

  // CSV Tab
  const dropzone = document.getElementById("dropzone");
  const csvFileInput = document.getElementById("csv-file-input");
  const selectedFileInfo = document.getElementById("selected-file-info");
  const selectedFileName = document.getElementById("selected-file-name");
  const btnClearFile = document.getElementById("btn-clear-file");
  const btnUploadCsv = document.getElementById("btn-upload-csv");
  const btnDownloadSampleCsv = document.getElementById("btn-download-sample-csv");

  // JSON Tab
  const rawJsonInput = document.getElementById("raw-json-input");
  const btnSubmitJson = document.getElementById("btn-submit-json");

  // Job Tracker
  const jobTracker = document.getElementById("job-tracker");
  const jobIdDisplay = document.getElementById("job-id-display");
  const jobStatusBadge = document.getElementById("job-status-badge");
  const btnCancelJob = document.getElementById("btn-cancel-job");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const statTotal = document.getElementById("stat-total");
  const statProcessed = document.getElementById("stat-processed");
  const statSuccessful = document.getElementById("stat-successful");
  const statFailed = document.getElementById("stat-failed");
  const jobErrorBanner = document.getElementById("job-error-banner");
  const certsTbody = document.getElementById("certs-tbody");

  // --- State ---
  let selectedFile = null;
  let currentJobId = null;
  let pollingInterval = null;

  // Error Formatter Helper (never shows [object Object])
  function formatApiError(data, status = 500) {
    if (!data) return `Request failed (HTTP ${status})`;
    if (typeof data === "string") return data;
    if (data.detail) {
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) {
        return data.detail
          .map(item => {
            if (typeof item === "string") return item;
            const loc = item.loc ? item.loc.filter(l => l !== "body").join(".") : "";
            return loc ? `${loc}: ${item.msg}` : (item.msg || JSON.stringify(item));
          })
          .join("; ");
      }
      if (typeof data.detail === "object") {
        return JSON.stringify(data.detail);
      }
    }
    if (data.message) return data.message;
    return JSON.stringify(data);
  }

  // Initialize API URL (defaults to live Render backend or current origin)
  const defaultApiUrl = window.location.host.includes("onrender.com")
    ? window.location.origin
    : "https://fastapi-server-x0dz.onrender.com";
  
  if (apiUrlInput) {
    apiUrlInput.value = defaultApiUrl;
    updateDocsLink(defaultApiUrl);
  }

  function getBaseUrl() {
    let url = apiUrlInput.value.trim();
    return url.replace(/\/+$/, "");
  }

  function updateDocsLink(url) {
    if (btnDocsLink) {
      btnDocsLink.href = `${url.replace(/\/+$/, "")}/docs`;
    }
  }

  apiUrlInput.addEventListener("input", () => {
    updateDocsLink(getBaseUrl());
  });

  // Today's date helper
  const todayStr = new Date().toISOString().split("T")[0];
  document.querySelectorAll(".rec-date").forEach(input => {
    if (!input.value) input.value = todayStr;
  });

  // --- Health Check ---
  async function checkHealth() {
    const baseUrl = getBaseUrl();
    healthText.textContent = "Connecting...";
    statusDot.style.backgroundColor = "var(--warning)";
    statusDot.style.boxShadow = "0 0 8px var(--warning)";
    statusBadge.style.color = "var(--warning)";
    statusBadge.style.borderColor = "rgba(245, 158, 11, 0.4)";

    try {
      const res = await fetch(`${baseUrl}/health`, { method: "GET" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.status === "healthy" || data.status === "degraded") {
        healthText.textContent = `Backend Online (${data.worker_queue || 'Ready'})`;
        statusDot.style.backgroundColor = "var(--success)";
        statusDot.style.boxShadow = "0 0 8px var(--success)";
        statusBadge.style.color = "#34d399";
        statusBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
      } else {
        healthText.textContent = `Issues: ${data.status}`;
        statusDot.style.backgroundColor = "var(--danger)";
        statusDot.style.boxShadow = "0 0 8px var(--danger)";
        statusBadge.style.color = "var(--danger)";
      }
    } catch (err) {
      healthText.textContent = "Offline / Unreachable";
      statusDot.style.backgroundColor = "var(--danger)";
      statusDot.style.boxShadow = "0 0 8px var(--danger)";
      statusBadge.style.color = "var(--danger)";
      statusBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
    }
  }

  btnCheckHealth.addEventListener("click", checkHealth);
  checkHealth();
  setInterval(checkHealth, 45000);

  // --- Tab Navigation ---
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
    });
  });

  // --- Interactive Form Rows ---
  function updateRemoveButtons() {
    const rows = recipientRows.querySelectorAll(".recipient-row");
    const removeBtns = recipientRows.querySelectorAll(".btn-remove");
    removeBtns.forEach(btn => {
      btn.disabled = rows.length <= 1;
    });
  }

  function createRecipientRow(name = "", course = "", date = todayStr) {
    const row = document.createElement("div");
    row.className = "recipient-row";
    row.innerHTML = `
      <input type="text" class="rec-name" placeholder="Full Name (required)" value="${name}" required>
      <input type="text" class="rec-course" placeholder="Course Name (default: Python)" value="${course}">
      <input type="date" class="rec-date" value="${date || todayStr}">
      <button type="button" class="btn btn-danger btn-icon btn-remove" title="Remove row">&times;</button>
    `;

    row.querySelector(".btn-remove").addEventListener("click", () => {
      if (recipientRows.children.length > 1) {
        row.remove();
        updateRemoveButtons();
      }
    });

    return row;
  }

  // Bind initial remove buttons
  recipientRows.querySelectorAll(".recipient-row").forEach(row => {
    const btn = row.querySelector(".btn-remove");
    if (btn) {
      btn.addEventListener("click", () => {
        if (recipientRows.children.length > 1) {
          row.remove();
          updateRemoveButtons();
        }
      });
    }
  });
  updateRemoveButtons();

  btnAddRow.addEventListener("click", () => {
    recipientRows.appendChild(createRecipientRow());
    updateRemoveButtons();
  });

  // --- CSV Handling ---
  dropzone.addEventListener("click", () => csvFileInput.click());

  ["dragenter", "dragover"].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  csvFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    if (!file.name.endsWith(".csv")) {
      alert("Please select a valid .csv file.");
      return;
    }
    selectedFile = file;
    selectedFileName.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    selectedFileInfo.style.display = "flex";
    btnUploadCsv.disabled = false;
  }

  btnClearFile.addEventListener("click", () => {
    selectedFile = null;
    csvFileInput.value = "";
    selectedFileInfo.style.display = "none";
    btnUploadCsv.disabled = true;
  });

  // Sample CSV generator
  btnDownloadSampleCsv.addEventListener("click", () => {
    const csvContent = "data:text/csv;charset=utf-8," + 
      "Name,Course,Date\n" +
      "Ada Lovelace,Computational Science,2026-10-08\n" +
      "Alan Turing,Cryptography,\n" +
      "Grace Hopper,,\n";
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "sample_recipients.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // --- Submit Handlers ---

  // 1. Interactive Form Submit
  interactiveForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const rows = recipientRows.querySelectorAll(".recipient-row");
    const certificates = [];

    rows.forEach(row => {
      const name = row.querySelector(".rec-name").value.trim();
      const course = row.querySelector(".rec-course").value.trim();
      const date = row.querySelector(".rec-date").value.trim();

      if (name) {
        const item = { name };
        if (course) item.course = course;
        if (date) item.date = date;
        certificates.push(item);
      }
    });

    if (certificates.length === 0) {
      alert("Please provide at least one recipient with a name.");
      return;
    }

    const payload = {
      certificates: certificates
    };

    await submitJsonJob(payload);
  });

  // 2. CSV Upload Submit
  btnUploadCsv.addEventListener("click", async () => {
    if (!selectedFile) return;

    const baseUrl = getBaseUrl();
    const formData = new FormData();
    formData.append("file", selectedFile);

    btnUploadCsv.disabled = true;
    btnUploadCsv.textContent = "Uploading & Enqueueing...";

    try {
      const res = await fetch(`${baseUrl}/api/v1/generate-certificate/csv`, {
        method: "POST",
        body: formData,
      });

      let data;
      try {
        data = await res.json();
      } catch (err) {
        data = { detail: `HTTP ${res.status} response` };
      }

      if (!res.ok) {
        throw new Error(formatApiError(data, res.status));
      }

      startTrackingJob(data.job_id);
    } catch (err) {
      alert(`Error submitting CSV: ${err.message}`);
    } finally {
      btnUploadCsv.disabled = false;
      btnUploadCsv.textContent = "Upload & Generate ⚡";
    }
  });

  // 3. Raw JSON Submit
  btnSubmitJson.addEventListener("click", async () => {
    try {
      let payload = JSON.parse(rawJsonInput.value);
      // Support both { certificates: [...] } and { recipients: [...] }
      if (!payload.certificates && payload.recipients) {
        payload.certificates = payload.recipients;
      }
      await submitJsonJob(payload);
    } catch (err) {
      alert(`Invalid JSON format: ${err.message}`);
    }
  });

  async function submitJsonJob(payload) {
    const baseUrl = getBaseUrl();
    try {
      const res = await fetch(`${baseUrl}/api/v1/generate-certificate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let data;
      try {
        data = await res.json();
      } catch (err) {
        data = { detail: `HTTP ${res.status} response` };
      }

      if (!res.ok) {
        throw new Error(formatApiError(data, res.status));
      }

      startTrackingJob(data.job_id);
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }

  // --- Job Tracking & Polling ---
  function startTrackingJob(jobId) {
    if (pollingInterval) clearInterval(pollingInterval);
    currentJobId = jobId;

    // Reset tracker UI
    jobTracker.classList.add("active");
    jobTracker.scrollIntoView({ behavior: "smooth" });
    jobIdDisplay.textContent = jobId;
    jobStatusBadge.className = "badge badge-processing";
    jobStatusBadge.textContent = "QUEUED";
    btnCancelJob.style.display = "inline-flex";
    jobErrorBanner.style.display = "none";
    progressBarFill.style.width = "0%";
    statTotal.textContent = "-";
    statProcessed.textContent = "0";
    statSuccessful.textContent = "0";
    statFailed.textContent = "0";

    certsTbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
          Background worker is processing recipients...
        </td>
      </tr>
    `;

    // Fetch immediately and poll
    pollJobStatus();
    pollingInterval = setInterval(pollJobStatus, 1200);
  }

  async function pollJobStatus() {
    if (!currentJobId) return;
    const baseUrl = getBaseUrl();

    try {
      const res = await fetch(`${baseUrl}/api/v1/generate-certificate/${currentJobId}`);
      if (!res.ok) {
        if (res.status === 404) {
          clearInterval(pollingInterval);
          jobStatusBadge.textContent = "NOT FOUND";
          jobStatusBadge.className = "badge badge-failed";
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }

      const job = await res.json();
      updateTrackerUI(job);

      // Terminal state check
      if (["completed", "failed", "cancelled"].includes(job.status)) {
        clearInterval(pollingInterval);
        pollingInterval = null;
        btnCancelJob.style.display = "none";
        await fetchCertificates(currentJobId);
      }
    } catch (err) {
      console.warn("Polling warning:", err);
    }
  }

  function updateTrackerUI(job) {
    const total = job.total !== undefined ? job.total : (job.total_certificates || 0);
    const successful = job.completed !== undefined ? job.completed : (job.successful_certificates || 0);
    const failed = job.failed !== undefined ? job.failed : (job.failed_certificates || 0);
    const processed = (successful + failed) || (job.processed_certificates || 0);
    const status = (job.status || "pending").toLowerCase();

    statTotal.textContent = total;
    statProcessed.textContent = processed;
    statSuccessful.textContent = successful;
    statFailed.textContent = failed;

    const percent = total > 0 ? Math.round((processed / total) * 100) : (status === "completed" ? 100 : 0);
    progressBarFill.style.width = `${percent}%`;

    jobStatusBadge.textContent = status.toUpperCase();
    if (status === "completed") {
      jobStatusBadge.className = "badge badge-completed";
    } else if (status === "failed") {
      jobStatusBadge.className = "badge badge-failed";
    } else if (status === "cancelled") {
      jobStatusBadge.className = "badge badge-failed";
    } else {
      jobStatusBadge.className = "badge badge-processing";
    }

    if (job.error_message || job.error) {
      jobErrorBanner.style.display = "block";
      jobErrorBanner.textContent = `Job Message: ${job.error_message || job.error}`;
    } else {
      jobErrorBanner.style.display = "none";
    }
  }

  // Cancel Job
  btnCancelJob.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (!confirm("Are you sure you want to cancel this certificate job?")) return;

    const baseUrl = getBaseUrl();
    try {
      btnCancelJob.disabled = true;
      const res = await fetch(`${baseUrl}/api/v1/generate-certificate/${currentJobId}`, {
        method: "DELETE"
      });
      let data;
      try {
        data = await res.json();
      } catch (e) {
        data = { detail: `HTTP ${res.status}` };
      }
      if (!res.ok) throw new Error(formatApiError(data, res.status));
      alert("Job marked as cancelled.");
      pollJobStatus();
    } catch (err) {
      alert(`Could not cancel job: ${err.message}`);
    } finally {
      btnCancelJob.disabled = false;
    }
  });

  // Fetch Certificate List
  async function fetchCertificates(jobId) {
    const baseUrl = getBaseUrl();
    try {
      const res = await fetch(`${baseUrl}/api/v1/generate-certificate/${jobId}/certificates`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderCertificatesTable(data.certificates || []);
    } catch (err) {
      certsTbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--danger); padding: 1.5rem;">
            Could not load certificates: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
  }

  function renderCertificatesTable(certs) {
    if (!certs || certs.length === 0) {
      certsTbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
            No certificate records found for this job.
          </td>
        </tr>
      `;
      return;
    }

    certsTbody.innerHTML = certs.map((cert, index) => {
      const statusClass = cert.status === "completed" ? "badge-completed" : (cert.status === "failed" ? "badge-failed" : "badge-pending");
      
      const name = cert.name || cert.recipient_name || "Recipient";
      const course = cert.course || cert.course_name || "Python";
      const url = cert.url || cert.s3_url;
      const errorMsg = cert.error || cert.error_message || "Failed";

      let actionHtml = `<span style="color: var(--text-muted);">-</span>`;
      if (cert.status === "completed" && url) {
        actionHtml = `<a href="${url}" target="_blank" rel="noopener noreferrer" class="btn-download">Download PDF 📄</a>`;
      } else if (cert.status === "failed") {
        actionHtml = `<span style="color: var(--danger); font-size: 0.8rem;" title="${escapeHtml(errorMsg)}">Failed: ${escapeHtml(errorMsg)}</span>`;
      }

      return `
        <tr>
          <td>${index + 1}</td>
          <td><strong>${escapeHtml(name)}</strong></td>
          <td>${escapeHtml(course)}</td>
          <td><span class="badge ${statusClass}">${cert.status.toUpperCase()}</span></td>
          <td>${actionHtml}</td>
        </tr>
      `;
    }).join("");
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
