(function () {
  const explicitApiBase = window.BAISED_API_BASE || "";
  const isStaticPreview =
    window.location.protocol === "file:" ||
    (["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port && window.location.port !== "5000");
  const API_BASE = (explicitApiBase || (isStaticPreview ? "http://127.0.0.1:5000" : "")).replace(/\/$/, "");
  const LAST_RESULT_KEY = "baised:last_fairness_result";
  let currentAnalysisResult = null;
  let datasetAnalysisResult = null;
  let modelAnalysisResult = null;
  let currentDatasetId = null;
  let currentModelDatasetId = null;
  let datasetScanRequestId = 0;
  let currentAiMarkdown = "";
  let currentMetrics = null;
  let currentDatasetMeta = null;
  let privacyModeEnabled = false;
  let sessionContainsPrivateWork = false;
  let currentSessionId = null;
  let recentSessions = [];
  let sessionSaveTimer = null;
  let sessionSaveInFlight = null;
  let restoringSession = false;
  let puppyPetCount = 0;

  function movePuppy() {
    const puppy = document.getElementById("the-puppy");
    const field = document.getElementById("puppy-field");
    if (!puppy || !field) return;

    const maxX = field.clientWidth - puppy.clientWidth;
    const currentX = parseFloat(puppy.style.left) || 0;
    const randomX = Math.random() * maxX;
    
    // Flip based on direction
    if (randomX > currentX) {
      puppy.style.transform = "scaleX(1)";
    } else {
      puppy.style.transform = "scaleX(-1)";
    }

    puppy.style.left = `${randomX}px`;
    
    // Tail wag speedup when moving
    const tail = document.getElementById("puppy-tail");
    if (tail) tail.style.animationDuration = "0.2s";
    setTimeout(() => {
      if (tail) tail.style.animationDuration = "0.8s";
    }, 700);
  }

  function setupPuppyInteractions() {
    const puppy = document.getElementById("the-puppy");
    const svg = document.getElementById("puppy-svg");
    const counter = document.getElementById("pet-count");
    
    if (!puppy) return;

    puppy.addEventListener("click", (e) => {
      e.stopPropagation();
      puppyPetCount++;
      if (counter) counter.textContent = puppyPetCount;
      
      // Bark/Jump Animation (Animation change)
      if (svg) {
        svg.style.transform = "translateY(-15px) rotate(-5deg)";
        setTimeout(() => {
          svg.style.transform = "translateY(0) rotate(0deg)";
        }, 300);
      }
      
      // Excited wag
      const tail = document.getElementById("puppy-tail");
      if (tail) tail.style.animationDuration = "0.1s";
      setTimeout(() => {
        if (tail) tail.style.animationDuration = "0.8s";
      }, 1200);
      
      movePuppy(); 
    });
    
    // Random roaming
    const roamInterval = setInterval(() => {
      const overlay = document.getElementById("puppy-overlay");
      if (overlay && !overlay.classList.contains("hidden")) {
        movePuppy();
      }
    }, 2500);
  }

  async function triggerPuppyDelay(taskFn) {
    const overlay = document.getElementById("puppy-overlay");
    const timer = document.getElementById("puppy-timer");
    const counter = document.getElementById("pet-count");
    const slowNotice = document.getElementById("puppy-slow-notice");
    
    if (!overlay) return await taskFn();

    // Reset state
    puppyPetCount = 0;
    if (counter) counter.textContent = "0";
    if (slowNotice) slowNotice.classList.add("hidden");
    overlay.classList.remove("hidden");
    overlay.classList.add("flex");
    
    let secondsLeft = 5;
    if (timer) timer.textContent = `${secondsLeft}s`;

    // Start task immediately in background
    let taskFinished = false;
    const taskPromise = taskFn().finally(() => {
      taskFinished = true;
    });
    
    // Force wait for at least 5 seconds
    await new Promise((resolve) => {
      const countdown = setInterval(() => {
        secondsLeft--;
        if (timer) timer.textContent = `${secondsLeft}s`;
        
        if (secondsLeft <= 0) {
          clearInterval(countdown);
          if (!taskFinished && slowNotice) {
            slowNotice.classList.remove("hidden");
          }
          resolve();
        }
      }, 1000);
    });

    try {
      return await taskPromise;
    } finally {
      overlay.classList.add("hidden");
      overlay.classList.remove("flex");
      if (slowNotice) slowNotice.classList.add("hidden");
    }
  }

  function persistLastResult(result) {
    if (privacyModeEnabled) {
      return;
    }
    try {
      localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(result || {}));
    } catch (error) {
      // Ignore storage failures (private mode / quota).
    }
  }

  function setSessionStatus(message) {
    setText("session-status-text", message);
    setText("mobile-session-status-text", message);
  }

  function hasSignedInUser() {
    return Boolean(window.baisedFirebase?.auth?.currentUser && window.baisedAuth?.getIdToken);
  }

  async function authFetch(path, options = {}) {
    if (!window.baisedAuth || typeof window.baisedAuth.getIdToken !== "function") {
      throw new Error("Sign in to save recent chats.");
    }
    const token = await window.baisedAuth.getIdToken();
    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    };
    return fetch(apiUrl(path), { ...options, headers });
  }

  async function parseErrorResponse(response, fallback) {
    const payload = await response.json().catch(() => ({}));
    if (response.ok) return payload;
    throw new Error(payload.error || payload.message || fallback);
  }

  function jsonClone(value) {
    return value === undefined ? null : JSON.parse(JSON.stringify(value));
  }

  function cleanResultForSession(result) {
    const cloned = jsonClone(result || null);
    if (!cloned || typeof cloned !== "object") return null;
    delete cloned.dataset_id;
    delete cloned.model_dataset_id;
    return cloned;
  }

  function deriveSessionTitle() {
    const result = currentAnalysisResult || datasetAnalysisResult || modelAnalysisResult;
    if (!result && currentDatasetMeta?.name) {
      return `Dataset audit: ${currentDatasetMeta.name}`.slice(0, 120);
    }
    if (!result) return "Untitled audit";
    const mode = result.mode === "model" ? "Model audit" : result.mode === "dataset" ? "Dataset audit" : "Bias check";
    const protectedAttr = result.protected_attribute || currentDatasetMeta?.protected_attr || "fairness";
    const severity = result.severity ? `${result.severity} ` : "";
    return `${mode}: ${severity}${protectedAttr}`.slice(0, 120);
  }

  function serializeWorkbenchState() {
    const activeResult = cleanResultForSession(currentAnalysisResult);
    const datasetResult = cleanResultForSession(datasetAnalysisResult);
    const modelResult = cleanResultForSession(modelAnalysisResult);
    return {
      title: deriveSessionTitle(),
      audit_mode: activeResult?.mode || "dataset",
      summary: activeResult
        ? {
            mode: activeResult.mode,
            severity: activeResult.severity,
            DIR: activeResult.DIR,
            difference: activeResult.difference,
            bias_score: activeResult.bias_score,
            protected_attribute: activeResult.protected_attribute,
            outcome_column: activeResult.outcome_column,
            row_count: activeResult.row_count,
          }
        : {},
      explanation: activeResult?.explanation || null,
      audit_result: activeResult,
      ai_chat: jsonClone(explainerHistory || []),
      ai_report_markdown: currentAiMarkdown || "",
      ai_report_source: document.getElementById("ai-model-name")?.textContent || "",
      dataset_meta: {
        name: currentDatasetMeta?.name || activeResult?.file_name || "",
        protected_attr: currentDatasetMeta?.protected_attr || activeResult?.protected_attribute || "",
        outcome: currentDatasetMeta?.outcome || activeResult?.outcome_column || "",
        row_count: activeResult?.row_count,
      },
      model_meta: activeResult?.model_audit
        ? {
            model_file_name: activeResult.model_audit.model_file_name,
            model_type: activeResult.model_audit.model_type,
          }
        : {},
      workspace_state: {
        active_result: activeResult,
        dataset_result: datasetResult,
        model_result: modelResult,
        current_ai_markdown: currentAiMarkdown || "",
        explainer_history: jsonClone(explainerHistory || []),
      },
    };
  }

  function renderRecentSessions() {
    const list = document.getElementById("recent-sessions-list");
    if (!list) return;
    list.innerHTML = "";
    if (!hasSignedInUser()) {
      list.innerHTML = '<div class="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-sm text-slate-500">Sign in to sync recent chats.</div>';
      return;
    }
    if (!recentSessions.length) {
      list.innerHTML = '<div class="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-sm text-slate-500">No saved chats yet.</div>';
      return;
    }
    recentSessions.forEach((session) => {
      const btn = document.createElement("button");
      const active = session.id === currentSessionId;
      btn.type = "button";
      btn.className = `w-full rounded-xl border px-3 py-3 text-left transition ${
        active ? "border-teal-300 bg-teal-50 text-teal-950" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
      }`;
      btn.innerHTML = `
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="truncate text-sm font-bold">${escapeHtml(session.title || "Untitled audit")}</div>
            <div class="mt-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
              <span>${escapeHtml(session.audit_mode || "audit")}</span>
              <span>${session.summary?.severity ? escapeHtml(session.summary.severity) : ""}</span>
            </div>
          </div>
          <span class="delete-session-btn inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-600" data-session-id="${escapeHtml(session.id)}" title="Delete chat">
            <span class="material-symbols-outlined text-base">delete</span>
          </span>
        </div>
      `;
      btn.addEventListener("click", () => loadSession(session.id));
      btn.querySelector(".delete-session-btn")?.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteSession(session.id, session.title || "this chat");
      });
      list.appendChild(btn);
    });
  }

  async function deleteSession(sessionId, title) {
    if (!sessionId || !hasSignedInUser()) return;
    const ok = confirm(`Delete "${title}" from Recent Chats? This cannot be undone.`);
    if (!ok) return;
    try {
      const response = await authFetch(`/api/auth/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
      });
      await parseErrorResponse(response, "Unable to delete chat.");
      if (sessionId === currentSessionId) {
        currentSessionId = null;
        currentAnalysisResult = null;
        datasetAnalysisResult = null;
        modelAnalysisResult = null;
        currentDatasetId = null;
        currentModelDatasetId = null;
        currentMetrics = null;
        currentDatasetMeta = null;
        currentAiMarkdown = "";
        explainerHistory = [];
        window.lastUploadedDatasetFile = null;
        clearWorkbenchForms();
        clearAiAnalyzerPanels();
        setAuditFlipMode("dataset");
        renderNeutralResult("dataset");
        restoreExplainerChat([]);
      }
      await loadRecentSessions();
      setSessionStatus("Chat deleted.");
    } catch (error) {
      setSessionStatus(error.message || "Unable to delete chat.");
    }
  }

  async function loadRecentSessions() {
    if (!hasSignedInUser()) {
      recentSessions = [];
      setSessionStatus("Sign in to save recent chats.");
      renderRecentSessions();
      return;
    }
    try {
      const response = await authFetch("/api/auth/sessions");
      const payload = await parseErrorResponse(response, "Unable to load recent chats.");
      recentSessions = payload.sessions || [];
      setSessionStatus(privacyModeEnabled ? "Privacy Mode: autosave is off." : "Recent chats sync to your account.");
      renderRecentSessions();
    } catch (error) {
      setSessionStatus(error.message || "Unable to load recent chats.");
    }
  }

  async function saveCurrentSession(options = {}) {
    if (restoringSession) return null;
    if (privacyModeEnabled && !options.force) return null;
    if (sessionContainsPrivateWork && !options.force) return null;
    if (Object.prototype.hasOwnProperty.call(options, "expectedSessionId") && options.expectedSessionId !== currentSessionId) {
      return null;
    }
    if (!hasSignedInUser()) {
      setSessionStatus("Sign in to save recent chats.");
      renderRecentSessions();
      return null;
    }
    const payload = serializeWorkbenchState();
    if (options.title) {
      payload.title = options.title;
    }
    payload.privacy_mode_saved = Boolean(options.privacyModeSaved);
    if (!options.allowEmpty && !payload.workspace_state.active_result && !payload.ai_chat.length && !payload.ai_report_markdown) {
      return null;
    }
    const expectedSessionId = options.expectedSessionId;
    const expectedSessionProvided = Object.prototype.hasOwnProperty.call(options, "expectedSessionId");
    try {
      const saveRequest = authFetch(
        currentSessionId ? `/api/auth/sessions/${encodeURIComponent(currentSessionId)}` : "/api/auth/sessions",
        {
          method: currentSessionId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      sessionSaveInFlight = saveRequest;
      const response = await saveRequest;
      if (sessionSaveInFlight === saveRequest) {
        sessionSaveInFlight = null;
      }
      const data = await parseErrorResponse(response, "Unable to save recent chat.");
      if (expectedSessionProvided && expectedSessionId !== currentSessionId) {
        await loadRecentSessions();
        return data.session || null;
      }
      currentSessionId = data.session?.id || currentSessionId;
      sessionContainsPrivateWork = false;
      sessionSaveTimer = null;
      setSessionStatus("Saved to Recent Chats.");
      await loadRecentSessions();
      return data.session;
    } catch (error) {
      sessionSaveInFlight = null;
      setSessionStatus(error.message || "Unable to save recent chat.");
      return null;
    }
  }

  function queueSessionSave() {
    if (privacyModeEnabled) {
      sessionContainsPrivateWork = true;
      updatePrivateSaveButton();
      return;
    }
    if (sessionContainsPrivateWork || restoringSession) return;
    window.clearTimeout(sessionSaveTimer);
    const expectedSessionId = currentSessionId;
    sessionSaveTimer = window.setTimeout(() => {
      sessionSaveTimer = null;
      saveCurrentSession({ expectedSessionId });
    }, 700);
  }

  async function flushSessionSave() {
    if (sessionSaveInFlight) {
      await sessionSaveInFlight.catch(() => null);
    }
    if (!sessionSaveTimer || privacyModeEnabled || sessionContainsPrivateWork || restoringSession) {
      return null;
    }
    window.clearTimeout(sessionSaveTimer);
    sessionSaveTimer = null;
    return saveCurrentSession();
  }

  function updatePrivateSaveButton() {
    document.querySelectorAll("[data-save-private-session], #save-private-session-btn").forEach((btn) => {
      btn.classList.toggle("hidden", !sessionContainsPrivateWork);
    });
  }

  function formatDecimal(value, digits) {
    const numeric = Number(value || 0);
    return numeric.toFixed(digits);
  }

  function formatPercent(value) {
    return `${formatDecimal(value, 1)}%`;
  }

  function formatSignedPercent(value) {
    const numeric = Number(value || 0);
    return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(1)}%`;
  }

  function severityTone(severity) {
    if (severity === "HIGH") {
      return {
        chip: "bg-red-100 text-red-700 border-red-200",
        meter: "#ef4444",
      };
    }

    if (severity === "MODERATE") {
      return {
        chip: "bg-amber-100 text-amber-700 border-amber-200",
        meter: "#f59e0b",
      };
    }

    return {
      chip: "bg-emerald-100 text-emerald-700 border-emerald-200",
      meter: "#10b981",
    };
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function renderEmptyState(id, message) {
    const container = document.getElementById(id);
    if (!container) {
      return;
    }
    container.innerHTML = `<div class="rounded-2xl border border-dashed border-outline-variant bg-surface-container-low px-4 py-5 text-sm text-slate-500">${message}</div>`;
  }

  function formatGroupObject(group) {
    if (!group || typeof group !== "object") {
      return "-";
    }
    return Object.entries(group)
      .map(([key, value]) => `${key}: ${value}`)
      .join(" | ");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatNullableDecimal(value, digits) {
    return value === null || value === undefined ? "-" : formatDecimal(value, digits);
  }

  function renderRecommendations(recommendations) {
    const container = document.getElementById("recommendations-list");
    if (!container) {
      return;
    }

    container.innerHTML = "";
    recommendations.forEach((item) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low px-4 py-4 text-sm leading-6 text-slate-700";
      card.textContent = item;
      container.appendChild(card);
    });
  }

  function renderHotspots(result) {
    const container = document.getElementById("hotspots-list");
    const chip = document.getElementById("hotspot-count-chip");
    if (!container || !chip) {
      return;
    }

    const hotspots = result.bias_hotspots || [];
    chip.textContent = `${hotspots.length} Hotspots`;
    container.innerHTML = "";

    if (!hotspots.length) {
      renderEmptyState("hotspots-list", "No hotspot data returned for this run.");
      return;
    }

    hotspots.forEach((hotspot) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      card.innerHTML = `
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-900">${formatGroupObject(hotspot.group)}</p>
            <p class="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">${hotspot.secondary_attribute || "Subgroup hotspot"}</p>
          </div>
          <span class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${hotspot.severity === "HIGH" ? "bg-red-100 text-red-700" : hotspot.severity === "MODERATE" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}">${hotspot.severity}</span>
        </div>
        <div class="mt-4 grid gap-3 sm:grid-cols-3">
          <div><p class="text-xs text-slate-500">DIR</p><p class="text-lg font-black text-slate-900">${formatDecimal(hotspot.DIR, 4)}</p></div>
          <div><p class="text-xs text-slate-500">Difference</p><p class="text-lg font-black text-slate-900">${formatDecimal(hotspot.difference, 4)}</p></div>
          <div><p class="text-xs text-slate-500">Sample Size</p><p class="text-lg font-black text-slate-900">${hotspot.sample_size ?? "-"}</p></div>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function renderSimulations(result) {
    const container = document.getElementById("simulations-list");
    const chip = document.getElementById("simulation-count-chip");
    if (!container || !chip) {
      return;
    }

    const simulations = result.simulations || [];
    chip.textContent = `${simulations.length} Scenarios`;
    container.innerHTML = "";

    if (!simulations.length) {
      renderEmptyState("simulations-list", "No simulations returned for this run.");
      return;
    }

    simulations.forEach((simulation) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      card.innerHTML = `
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-900">${simulation.scenario}</p>
            <p class="mt-1 text-sm leading-6 text-slate-600">${simulation.details || ""}</p>
          </div>
          <span class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${simulation.bias_reduced ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"}">${simulation.bias_reduced ? "Improves Bias" : "No Gain"}</span>
        </div>
        <div class="mt-3">
          <p class="text-xs text-slate-500">New DIR</p>
          <p class="text-lg font-black text-slate-900">${formatDecimal(simulation.new_DIR, 4)}</p>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function renderRepairs(result) {
    const container = document.getElementById("repairs-list");
    const chip = document.getElementById("repair-count-chip");
    if (!container || !chip) {
      return;
    }

    const repairs = result.repair_suggestions || [];
    chip.textContent = `${repairs.length} Suggestions`;
    container.innerHTML = "";

    if (!repairs.length) {
      renderEmptyState("repairs-list", "No repair suggestions returned for this run.");
      return;
    }

    repairs.forEach((repair) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      card.innerHTML = `
        <p class="text-sm font-semibold text-slate-900">${repair.action || "Repair suggestion"}</p>
        <p class="mt-2 text-sm leading-6 text-slate-600">${repair.reason || ""}</p>
        <div class="mt-3 flex flex-wrap gap-4 text-sm">
          <span class="font-semibold text-slate-900">${repair.required_change ? `Required Change ${repair.required_change}` : "Targeted calibration review"}</span>
          <span class="text-slate-500">${repair.target_DIR !== undefined ? `Target DIR ${repair.target_DIR}` : ""}</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function renderFeatureImpact(result) {
    const container = document.getElementById("feature-impact-list");
    const chip = document.getElementById("feature-count-chip");
    if (!container || !chip) {
      return;
    }

    const ranking = result.feature_impact_ranking || [];
    chip.textContent = `${ranking.length} Features`;
    container.innerHTML = "";

    if (!ranking.length) {
      renderEmptyState("feature-impact-list", "No feature impact ranking returned for this run.");
      return;
    }

    ranking.forEach((item, index) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      const width = Math.max(4, Math.min(100, Number(item.impact || 0) * 100));
      card.innerHTML = `
        <div class="mb-3 flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-900">${item.feature}</p>
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">Rank ${index + 1}</p>
          </div>
          <p class="text-sm font-black text-slate-900">${formatDecimal(item.impact || 0, 4)}</p>
        </div>
        <div class="h-3 rounded-full bg-slate-200">
          <div class="meter-fill h-3 rounded-full bg-secondary" style="width: ${width}%"></div>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function renderWarnings(result) {
    const container = document.getElementById("warnings-list");
    const chip = document.getElementById("warning-count-chip");
    if (!container || !chip) {
      return;
    }

    const warnings = result.warnings || [];
    chip.textContent = `${warnings.length} Warnings`;
    container.innerHTML = "";

    if (!warnings.length) {
      renderEmptyState("warnings-list", "No reliability warnings for this run.");
      return;
    }

    warnings.forEach((warning) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-900";
      card.textContent = warning;
      container.appendChild(card);
    });
  }

  function riskTone(level) {
    const normalized = String(level || "").toUpperCase();
    if (normalized === "HIGH") return "wb-badge-danger";
    if (normalized === "MEDIUM" || normalized === "MODERATE" || normalized === "AMBER") return "wb-badge-warning";
    return "wb-badge-safe";
  }

  function renderProxyAnalysis(result) {
    const container = document.getElementById("proxy-analysis-list");
    const chip = document.getElementById("proxy-count-chip");
    if (!container || !chip) return;

    const proxies = result.proxy_analysis || [];
    chip.textContent = `${proxies.length} Found`;
    container.innerHTML = "";

    chip.className = "wb-badge";
    if (proxies.length === 0) {
      chip.classList.add("wb-badge-safe");
    } else {
      const hasHighRisk = proxies.some(p => String(p.risk).toUpperCase() === "HIGH");
      if (hasHighRisk) {
        chip.classList.add("wb-badge-danger");
      } else {
        chip.classList.add("wb-badge-warning");
      }
    }

    if (!proxies.length) {
      container.innerHTML = `<p class="text-sm leading-6 text-slate-500">No strong proxy feature signals were detected.</p>`;
      return;
    }

    proxies.slice(0, 4).forEach((item) => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      card.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm font-bold text-slate-900">${item.feature}</p>
            <p class="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Proxy for ${item.proxy_for}</p>
          </div>
          <span class="wb-badge ${riskTone(item.risk)}">${item.risk}</span>
        </div>
        <p class="mt-3 text-sm leading-6 text-slate-600">Association score ${formatDecimal(item.association_score || 0, 4)}</p>
      `;
      container.appendChild(card);
    });
  }

  function renderDatasetRisk(result) {
    const risk = result.dataset_risk || {};
    const chip = document.getElementById("risk-level-chip");
    const score = document.getElementById("dataset-risk-score");
    const confidence = document.getElementById("dataset-risk-confidence");
    const factors = document.getElementById("dataset-risk-factors");
    if (!chip || !score || !confidence || !factors) return;

    const hasRisk = risk.risk_score !== undefined || Array.isArray(risk.factors);
    chip.textContent = hasRisk ? (risk.risk_level || "LOW") : "Not Run";
    
    chip.className = "wb-badge";
    if (hasRisk) {
      chip.classList.add(riskTone(risk.risk_level));
    } else {
      chip.classList.add("wb-badge-neutral");
    }

    score.textContent = risk.risk_score !== undefined ? `${risk.risk_score}/100` : "--";
    confidence.textContent = risk.confidence ? `Audit confidence: ${risk.confidence}` : "Confidence unavailable.";
    factors.innerHTML = "";

    const items = risk.factors || [];
    if (!items.length) {
      factors.innerHTML = `<p class="text-sm leading-6 text-slate-500">No reliability factors available.</p>`;
      return;
    }

    items.slice(0, 4).forEach((item) => {
      const row = document.createElement("div");
      row.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      row.innerHTML = `
        <p class="text-sm font-bold text-slate-900">${escapeHtml(String(item.factor || "Risk").replaceAll("_", " "))}</p>
        <p class="mt-1 text-sm leading-6 text-slate-600">${escapeHtml(item.detail || "")}</p>
      `;
      factors.appendChild(row);
    });
  }

  function renderBiasPattern(result) {
    const pattern = result.bias_pattern || {};
    const type = document.getElementById("bias-pattern-type");
    const action = document.getElementById("bias-pattern-action");
    const chip = document.getElementById("pattern-confidence-chip");
    const evidence = document.getElementById("bias-pattern-evidence");
    if (!type || !action || !chip || !evidence) return;

    type.textContent = pattern.pattern_type ? String(pattern.pattern_type).replaceAll("_", " ") : "No pattern yet";
    action.textContent = pattern.recommended_action || "Run a dataset audit to classify the bias pattern.";
    
    chip.className = "wb-badge";
    if (pattern.confidence === undefined || !pattern.pattern_type) {
      chip.textContent = "--";
      chip.classList.add("wb-badge-neutral");
    } else {
      const confPercent = Math.round(pattern.confidence * 100);
      chip.textContent = `${confPercent}%`;
      if (confPercent >= 70) {
        chip.classList.add("wb-badge-danger");
      } else if (confPercent >= 40) {
        chip.classList.add("wb-badge-warning");
      } else {
        chip.classList.add("wb-badge-neutral");
      }
    }

    evidence.innerHTML = "";

    const items = pattern.evidence || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "rounded-2xl bg-surface-container-low px-4 py-3";
      li.textContent = "No pattern evidence available yet.";
      evidence.appendChild(li);
      return;
    }

    items.slice(0, 4).forEach((item) => {
      const li = document.createElement("li");
      li.className = "rounded-2xl bg-surface-container-low px-4 py-3";
      li.textContent = item;
      evidence.appendChild(li);
    });
  }

  function setExportState(enabled, message) {
    const colabBtn = document.getElementById("export-colab-btn");
    const whatIfBtn = document.getElementById("export-what-if-btn");
    const status = document.getElementById("export-status-text");
    [colabBtn, whatIfBtn].forEach((button) => {
      if (button) button.disabled = !enabled;
    });
    if (status) {
      status.textContent = message || (enabled ? "Exports are ready for this standardized dataset." : "Run a dataset audit before exporting.");
    }
  }

  function buildExportUrl(kind) {
    if (!currentDatasetId || !currentAnalysisResult) return "";
    const params = new URLSearchParams();
    if (currentAnalysisResult.protected_attribute) {
      params.set("protected_attribute", currentAnalysisResult.protected_attribute);
    }
    if (currentAnalysisResult.outcome_column) {
      params.set("outcome_column", currentAnalysisResult.outcome_column);
    }
    if (currentAnalysisResult.qualification_column) {
      params.set("qualification_column", currentAnalysisResult.qualification_column);
    }
    const query = params.toString();
    return `/api/export/${kind}/${encodeURIComponent(currentDatasetId)}${query ? `?${query}` : ""}`;
  }

  function renderFieldAnalysis(result) {
    const container = document.getElementById("field-analysis-body");
    const chip = document.getElementById("field-count-chip");
    if (!container || !chip) return;

    const profile = (result.stats && result.stats.column_profile) || {};
    const columns = Object.keys(profile);
    chip.textContent = `${columns.length} Fields`;
    container.innerHTML = "";

    if (!columns.length) {
      container.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500 italic">No field analysis available.</td></tr>`;
      return;
    }

    columns.forEach((name) => {
      const data = profile[name];
      const analysis = data.analysis || {};
      const type = data.is_numeric ? "Numeric" : data.categorical_like ? "Categorical" : "Object";
      
      let rangeText = "-";
      if (data.is_numeric && analysis.min !== null) {
        rangeText = `${analysis.min} to ${analysis.max} (μ=${analysis.mean})`;
      } else if (analysis.top_values) {
        rangeText = Object.keys(analysis.top_values).slice(0, 3).join(", ");
      }

      const row = document.createElement("tr");
      row.className = "hover:bg-slate-50 transition-colors";
      
      let recommendationBadge = "";
      if (data.group_score > 3.0) {
        recommendationBadge = '<span class="ml-2 text-[10px] bg-secondary/10 text-secondary px-1.5 py-0.5 rounded-full font-bold uppercase">Rec. Protected</span>';
      } else if (data.outcome_score > 4.5) {
        recommendationBadge = '<span class="ml-2 text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded-full font-bold uppercase">Rec. Outcome</span>';
      }

      row.innerHTML = `
        <td class="px-4 py-4 font-semibold text-slate-900">
          ${name}
          ${recommendationBadge}
        </td>
        <td class="px-4 py-4 text-slate-600">${type} ${data.identifier_like ? '<span class="ml-2 text-[10px] bg-slate-100 px-1 rounded">ID-like</span>' : ''}</td>
        <td class="px-4 py-4 text-slate-600">${data.unique_count}</td>
        <td class="px-4 py-4 text-slate-600">${analysis.missing_count} (${(analysis.missing_ratio * 100).toFixed(1)}%)</td>
        <td class="px-4 py-4 text-slate-600 font-mono text-xs">${rangeText}</td>
      `;
      container.appendChild(row);
    });
  }

  function renderGroupBars(result) {
    const container = document.getElementById("group-bars");
    const groupCountChip = document.getElementById("group-count-chip");
    if (!container || !groupCountChip) {
      return;
    }

    const rankings = (result.stats && result.stats.group_rankings) || [];
    groupCountChip.textContent = `${rankings.length} Groups`;
    container.innerHTML = "";

    rankings.forEach((entry, index) => {
      const isTop = entry.group === result.most_advantaged_group;
      const isBottom = entry.group === result.least_advantaged_group;
      const bar = document.createElement("div");
      bar.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";

      const label = document.createElement("div");
      label.className = "mb-3 flex items-center justify-between gap-4";
      label.innerHTML = `
        <div>
          <p class="text-sm font-semibold text-slate-900">${entry.group}</p>
          <p class="text-xs uppercase tracking-[0.18em] text-slate-500">${isTop ? "Most advantaged" : isBottom ? "Least advantaged" : `Rank ${index + 1}`}</p>
        </div>
        <p class="text-sm font-bold text-slate-900">${formatPercent(entry.selection_rate * 100)}</p>
      `;

      const meter = document.createElement("div");
      meter.className = "h-3 rounded-full bg-slate-200";

      const fill = document.createElement("div");
      fill.className = "meter-fill h-3 rounded-full";
      fill.style.width = `${Math.max(4, entry.selection_rate * 100)}%`;
      fill.style.backgroundColor = isBottom ? "#ba1a1a" : isTop ? "#3a6662" : "#111827";

      meter.appendChild(fill);
      bar.appendChild(label);
      bar.appendChild(meter);
      container.appendChild(bar);
    });
  }

  const ADVANCED_METRIC_LABELS = {
    demographic_parity_difference: "Demographic Parity Difference",
    demographic_parity_ratio: "Demographic Parity Ratio",
    equalized_odds_difference: "Equalized Odds Difference",
    equal_opportunity_difference: "Equal Opportunity Difference",
  };

  const ADVANCED_RULES = [
    {
      name: "Demographic Parity",
      target: "DP ratio >= 0.8",
      metric: "Selection-rate parity across sensitive groups.",
    },
    {
      name: "Equal Opportunity",
      target: "|EOD| <= 0.1",
      metric: "Qualified positive-rate gap across groups.",
    },
    {
      name: "Equalized Odds",
      target: "|AOD| <= 0.1",
      metric: "Average error tradeoff gap across groups.",
    },
  ];

  function metricVisualValue(row, metricKey) {
    if (metricKey === "demographic_parity_ratio") {
      return Number(row.demographic_parity_ratio || 0);
    }
    if (metricKey === "demographic_parity_difference") {
      return Number(row.demographic_parity_difference || 0);
    }
    if (metricKey === "equal_opportunity_difference") {
      return Number(row.equal_opportunity_rate || 0);
    }
    return Number(row.equal_opportunity_rate ?? row.selection_rate ?? 0);
  }

  function renderAdvancedMetricVisual(advancedFairness, metricKey) {
    const container = document.getElementById("advanced-metric-visual");
    const title = document.getElementById("advanced-visual-title");
    const subtitle = document.getElementById("advanced-visual-subtitle");
    const scale = document.getElementById("advanced-visual-scale");
    if (!container) return;

    const frame = advancedFairness?.metric_frame || [];
    const metricLabel = ADVANCED_METRIC_LABELS[metricKey] || "Metric Profile";
    if (title) title.textContent = `${metricLabel} Profile`;
    if (subtitle) {
      subtitle.textContent = metricKey === "demographic_parity_ratio"
        ? "Higher bars are closer to the best observed group."
        : metricKey === "demographic_parity_difference"
          ? "Shorter bars indicate less distance from the best observed group."
          : "Bars compare qualified positive-rate behavior by group.";
    }

    container.innerHTML = "";
    if (!frame.length) {
      container.innerHTML = '<div class="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900">Metric visual appears after analysis.</div>';
      return;
    }

    const values = frame.map((row) => metricVisualValue(row, metricKey));
    const maxValue = Math.max(1, ...values);
    const minValue = Math.min(...values);
    if (scale) scale.textContent = `${formatDecimal(minValue, 2)} - ${formatDecimal(maxValue, 2)}`;

    frame.forEach((row) => {
      const value = metricVisualValue(row, metricKey);
      const width = Math.max(4, Math.min(100, (value / maxValue) * 100));
      const isLeast = row.advantage === "least_advantaged";
      const isMost = row.advantage === "most_advantaged";
      const barClass = isLeast
        ? "bg-red-500"
        : isMost
          ? "bg-emerald-500"
          : "bg-indigo-500";

      const item = document.createElement("div");
      item.className = "rounded-xl bg-white p-4 shadow-sm dark:bg-zinc-900";
      item.innerHTML = `
        <div class="mb-2 flex items-center justify-between gap-3">
          <p class="text-sm font-bold text-slate-950 dark:text-white">${escapeHtml(row.group)}</p>
          <p class="font-mono text-xs font-bold text-slate-600 dark:text-zinc-300">${formatDecimal(value, 4)}</p>
        </div>
        <div class="relative h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-zinc-800">
          <div class="h-3 rounded-full ${barClass} transition-all duration-300 ease-out" style="width: ${width}%"></div>
        </div>
        <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>${row.sample_size ?? "-"} rows</span>
          <span>${formatPercent((row.selection_rate || 0) * 100)} selected</span>
        </div>
      `;
      container.appendChild(item);
    });
  }

  function renderAdvancedMetricFrame(advancedFairness) {
    const container = document.getElementById("advanced-metric-frame-body");
    const featureChip = document.getElementById("advanced-feature-chip");
    if (!container) return;

    const frame = advancedFairness?.metric_frame || [];
    const sensitiveFeatures = advancedFairness?.sensitive_features || [];
    if (featureChip) {
      featureChip.textContent = sensitiveFeatures.length
        ? `${sensitiveFeatures.join(" x ")}`
        : `${frame.length} Groups`;
    }

    container.innerHTML = "";
    if (!frame.length) {
      container.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500 italic">No advanced subgroup metrics available.</td></tr>';
      return;
    }

    frame.forEach((row) => {
      const roleLabel = row.advantage === "most_advantaged"
        ? "Most advantaged"
        : row.advantage === "least_advantaged"
          ? "Least advantaged"
          : "Comparison";
      const roleClass = row.advantage === "least_advantaged"
        ? "bg-red-50 text-red-700"
        : row.advantage === "most_advantaged"
          ? "bg-emerald-50 text-emerald-700"
          : "bg-slate-100 text-slate-600";

      const tr = document.createElement("tr");
      tr.className = "bg-white dark:bg-zinc-900";
      tr.innerHTML = `
        <td class="px-4 py-4 font-semibold text-slate-950 dark:text-zinc-100">${escapeHtml(row.group)}</td>
        <td class="px-4 py-4 text-slate-600 dark:text-zinc-400">${row.sample_size ?? "-"}</td>
        <td class="px-4 py-4 text-slate-900 dark:text-zinc-100">${formatPercent((row.selection_rate || 0) * 100)}</td>
        <td class="px-4 py-4 font-mono text-xs text-slate-700 dark:text-zinc-300">${formatNullableDecimal(row.demographic_parity_ratio, 4)}</td>
        <td class="px-4 py-4 font-mono text-xs text-slate-700 dark:text-zinc-300">${formatNullableDecimal(row.demographic_parity_difference, 4)}</td>
        <td class="px-4 py-4 font-mono text-xs text-slate-700 dark:text-zinc-300">${formatNullableDecimal(row.equal_opportunity_rate, 4)}</td>
        <td class="px-4 py-4"><span class="rounded-full px-2.5 py-1 text-xs font-bold ${roleClass}">${roleLabel}</span></td>
      `;
      container.appendChild(tr);
    });
  }

  function renderCustomMetricRules(advancedFairness) {
    const container = document.getElementById("custom-metric-rule-list");
    if (!container) return;

    const metrics = advancedFairness?.metrics?.metrics || {};
    container.innerHTML = "";
    ADVANCED_RULES.forEach((rule) => {
      const active = rule.name === "Demographic Parity"
        ? Number(metrics.demographic_parity_ratio || 0) >= 0.8
        : Math.abs(Number(rule.name === "Equal Opportunity" ? metrics.equal_opportunity_difference : metrics.equalized_odds_difference) || 0) <= 0.1;
      const card = document.createElement("div");
      card.className = "rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900";
      card.innerHTML = `
        <div class="flex items-center justify-between gap-3">
          <p class="text-sm font-bold text-slate-950 dark:text-white">${rule.name}</p>
          <span class="rounded-full px-2 py-0.5 text-xs font-bold ${active ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}">${active ? "Pass" : "Review"}</span>
        </div>
        <p class="mt-1 text-xs text-slate-600 dark:text-zinc-400">${rule.metric}</p>
        <p class="mt-2 font-mono text-xs text-slate-500">${rule.target}</p>
      `;
      container.appendChild(card);
    });
  }

  function bindCustomMetricEvaluator(advancedFairness) {
    const metricSelect = document.getElementById("custom-metric-select");
    const thresholdInput = document.getElementById("custom-metric-threshold");
    const evaluation = document.getElementById("custom-metric-evaluation");
    if (!metricSelect || !thresholdInput || !evaluation) return;

    const metrics = advancedFairness?.metrics?.metrics || {};
    const evaluate = () => {
      const metricKey = metricSelect.value;
      const threshold = Number(thresholdInput.value || 0);
      const value = Number(metrics[metricKey] || 0);
      const higherIsBetter = metricKey === "demographic_parity_ratio";
      const passes = higherIsBetter ? value >= threshold : Math.abs(value) <= threshold;
      evaluation.className = `mt-3 rounded-xl border px-4 py-3 text-sm ${
        passes
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }`;
      evaluation.innerHTML = `
        <div class="flex items-center justify-between gap-3">
          <span class="font-bold">${ADVANCED_METRIC_LABELS[metricKey] || "Custom Metric"}</span>
          <span class="rounded-full bg-white/70 px-2 py-0.5 text-xs font-black">${passes ? "Pass" : "Review"}</span>
        </div>
        <p class="mt-1 font-mono text-xs">value ${formatDecimal(value, 4)} ${higherIsBetter ? ">=" : "<="} threshold ${formatDecimal(threshold, 2)}</p>
      `;
    };

    metricSelect.removeEventListener("change", window._customMetricEvaluateHandler);
    thresholdInput.removeEventListener("input", window._customMetricEvaluateHandler);
    window._customMetricEvaluateHandler = evaluate;
    metricSelect.addEventListener("change", window._customMetricEvaluateHandler);
    thresholdInput.addEventListener("input", window._customMetricEvaluateHandler);
    evaluate();
  }

  function renderIntersectional(intersectional) {
    const container = document.getElementById("intersectional-list");
    const countChip = document.getElementById("intersectional-count-chip");
    if (!container) return;
    
    container.innerHTML = "";
    if (countChip) countChip.textContent = `${(intersectional || []).length} Groups`;
    if (!intersectional || !intersectional.length) {
      container.innerHTML = '<div class="rounded-2xl border border-dashed border-outline-variant bg-surface-container-low px-4 py-5 text-sm text-slate-500">No intersectional data available.</div>';
      return;
    }

    intersectional.forEach(data => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      const groupName = typeof data.group === "object" ? Object.entries(data.group).map(([k, v]) => `${k}:${v}`).join(" & ") : data.group;
      const dir = Number(data.DIR || 0);
      card.innerHTML = `
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-bold text-slate-900 dark:text-zinc-100">${escapeHtml(groupName)}</p>
            <p class="mt-1 text-xs text-slate-500 dark:text-zinc-400">Sample size: ${data.sample_size}</p>
          </div>
          <div class="text-right">
            <p class="text-sm font-black text-slate-950 dark:text-white">${formatPercent(data.selection_rate * 100)}</p>
            <p class="text-xs font-semibold ${dir < 0.8 ? "text-red-700" : "text-emerald-700"}">DIR ${formatDecimal(dir, 4)}</p>
          </div>
        </div>
        <div class="mt-3 h-2 rounded-full bg-slate-200">
          <div class="h-2 rounded-full ${dir < 0.8 ? "bg-red-500" : "bg-emerald-500"}" style="width: ${Math.max(4, Math.min(100, dir * 100))}%"></div>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function renderMitigations(mitigations) {
    const container = document.getElementById("algorithmic-mitigation-list");
    const countChip = document.getElementById("advanced-mitigation-count-chip");
    if (!container) return;

    container.innerHTML = "";
    if (countChip) countChip.textContent = `${(mitigations || []).length} Paths`;
    if (!mitigations || !mitigations.length) {
      container.innerHTML = '<div class="rounded-2xl border border-dashed border-outline-variant bg-surface-container-low px-4 py-5 text-sm text-slate-500">No mitigation suggestions available.</div>';
      return;
    }

    mitigations.forEach(mitigation => {
      const card = document.createElement("div");
      card.className = "rounded-2xl border border-outline-variant bg-surface-container-low p-4";
      card.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <p class="text-sm font-bold text-slate-900 dark:text-zinc-100">${escapeHtml(mitigation.strategy)}</p>
          <span class="shrink-0 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700">${escapeHtml(mitigation.type || "Mitigation")}</span>
        </div>
        <p class="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-400">${escapeHtml(mitigation.description)}</p>
        <p class="mt-3 font-mono text-xs text-slate-500">${mitigation.type === "Post-processing" ? "threshold_adjustment.fit(...)" : mitigation.type === "In-processing" ? "constrained_optimizer.fit(...)" : "correlation_filter.transform(...)"}</p>
      `;
      container.appendChild(card);
    });
  }

  function renderResult(result) {
    const isKnownResult = result.mode === "model"
      ? result === modelAnalysisResult
      : result === datasetAnalysisResult;
    currentAnalysisResult = result;
    if (result.mode === "model") {
      modelAnalysisResult = result;
    } else {
      datasetAnalysisResult = result;
    }
    if (result.dataset_id) {
      currentDatasetId = result.dataset_id;
    }
    if (result.mode === "model") {
      setAuditFlipMode("model");
    } else {
      setAuditFlipMode("dataset");
    }
    const tone = severityTone(result.severity);
    setText("result-mode-chip", result.mode === "model" ? "Model" : result.mode === "dataset" ? "Dataset" : "Simple");
    setText("severity-text", result.severity);
    setText("bias-detected-text", result.bias_detected ? "Bias detected below the 0.8 DIR threshold." : "No bias detected under the 0.8 DIR threshold.");
    setText("bias-score-text", formatDecimal(result.bias_score, 1));
    setText("dir-text", formatDecimal(result.DIR, 4));
    setText("difference-text", formatDecimal(result.difference, 4));
    setText("parity-text", formatPercent(result.stats.parity_percent));
    setText("eod-text", formatDecimal(result.metrics?.EOD || 0, 4));
    setText("aod-text", formatDecimal(result.metrics?.AOD || 0, 4));
    renderExplanation(result.explanation);
    setText("advantaged-group-text", result.most_advantaged_group);
    setText("disadvantaged-group-text", result.least_advantaged_group);
    setText("selection-gap-percent-text", formatPercent(result.stats.selection_gap_percent));
    setText("influential-feature-text", result.most_influential_feature || "-");
    setText("hidden-bias-text", result.hidden_bias_detected ? "Yes" : "No");

    const metaTextElement = document.getElementById("dataset-meta-text");
    if (metaTextElement) {
      if (result.mode === "dataset" || result.mode === "model") {
        const rowsVal = result.row_count !== undefined ? `${result.row_count.toLocaleString()} rows` : "";
        const protVal = result.protected_attribute ? `Protected attribute: ${result.protected_attribute}` : "";
        const outVal = result.outcome_column ? `${result.mode === "model" ? "Prediction" : "Outcome"}: ${result.outcome_column}` : "";
        
        // Human-readable summary
        const summaryParts = [];
        summaryParts.push(result.mode === "model" ? "Model audit" : "Uploaded dataset");
        if (rowsVal) summaryParts.push(rowsVal);
        if (protVal) summaryParts.push(protVal);
        if (outVal) summaryParts.push(outVal);
        
        const summaryLine = summaryParts.join(" · ");
        
        // Technical metadata
        const techParts = [];
        if (result.file_name) {
          techParts.push(`<p><strong>Filename:</strong> ${escapeHtml(result.file_name)}</p>`);
        }
        if (result.model_audit) {
          techParts.push(`<p><strong>Model:</strong> ${escapeHtml(result.model_audit.model_file_name)}</p>`);
          techParts.push(`<p><strong>Loader:</strong> ${escapeHtml(result.model_audit.model_type)}</p>`);
        }
        if (result.derived_protected && result.derived_protected.source_column) {
          techParts.push(`<p><strong>Derived groups:</strong> ${escapeHtml(result.derived_protected.source_column)} via ${escapeHtml(result.derived_protected.strategy)}</p>`);
        }
        if (result.derived_outcome && result.derived_outcome.source_column) {
          techParts.push(`<p><strong>Derived outcome:</strong> ${escapeHtml(result.derived_outcome.source_column)} &gt;= ${escapeHtml(result.derived_outcome.threshold)}</p>`);
        }
        if (result.model_performance_by_group?.disparities) {
          const gaps = result.model_performance_by_group.disparities;
          if (gaps.error_rate_gap !== null && gaps.error_rate_gap !== undefined) {
            techParts.push(`<p><strong>Error gap:</strong> ${formatDecimal(gaps.error_rate_gap, 4)}</p>`);
          }
          if (gaps.true_positive_rate_gap !== null && gaps.true_positive_rate_gap !== undefined) {
            techParts.push(`<p><strong>TPR gap:</strong> ${formatDecimal(gaps.true_positive_rate_gap, 4)}</p>`);
          }
          if (gaps.false_positive_rate_gap !== null && gaps.false_positive_rate_gap !== undefined) {
            techParts.push(`<p><strong>FPR gap:</strong> ${formatDecimal(gaps.false_positive_rate_gap, 4)}</p>`);
          }
        }

        const techHtml = techParts.length > 0 ? `
          <div class="mt-2">
            <button type="button" id="file-details-toggle-btn" class="text-xs text-teal-600 hover:text-teal-700 font-semibold underline cursor-pointer focus:outline-none flex items-center gap-1">
              <span class="material-symbols-outlined text-[14px]">info</span>
              <span id="file-details-toggle-text">Show file info</span>
            </button>
            <div id="file-details-container" class="hidden mt-2 rounded-xl bg-slate-50 dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 p-3 text-xs text-slate-500 dark:text-zinc-400 space-y-1">
              ${techParts.join("")}
            </div>
          </div>
        ` : "";
        
        metaTextElement.innerHTML = `
          <div>
            <p class="text-sm leading-6 text-slate-600 dark:text-zinc-300 font-medium">${escapeHtml(summaryLine)}</p>
            ${techHtml}
          </div>
        `;
        
        // Add toggle event listener
        const toggleBtn = document.getElementById("file-details-toggle-btn");
        if (toggleBtn) {
          toggleBtn.addEventListener("click", () => {
            const container = document.getElementById("file-details-container");
            const toggleText = document.getElementById("file-details-toggle-text");
            if (container && toggleText) {
              const isHidden = container.classList.contains("hidden");
              if (isHidden) {
                container.classList.remove("hidden");
                toggleText.textContent = "Hide file info";
              } else {
                container.classList.add("hidden");
                toggleText.textContent = "Show file info";
              }
            }
          });
        }
      } else {
        metaTextElement.innerHTML = `<p class="text-sm leading-6 text-slate-600 dark:text-zinc-300">Simple input mode using groupA and groupB percentages.</p>`;
      }
    }

    const biasScoreBar = document.getElementById("bias-score-bar");
    if (biasScoreBar) {
      biasScoreBar.style.width = `${Math.min(100, Math.max(0, Number(result.bias_score || 0)))}%`;
      biasScoreBar.style.backgroundColor = tone.meter;
    }

    const severityText = document.getElementById("severity-text");
    if (severityText) {
      severityText.className = "mt-3 text-3xl font-black";
      severityText.style.color = tone.meter;
    }

    const chip = document.getElementById("result-mode-chip");
    if (chip) {
      chip.className = `rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${tone.chip}`;
    }

    renderRecommendations(result.recommendations || []);
    renderFieldAnalysis(result);
    renderGroupBars(result);
    renderHotspots(result);
    renderSimulations(result);
    renderRepairs(result);
    renderFeatureImpact(result);
    renderWarnings(result);
    renderProxyAnalysis(result);
    renderDatasetRisk(result);
    renderBiasPattern(result);
    setExportState(Boolean(currentDatasetId && (result.mode === "dataset" || result.mode === "model")), "Exports are ready for this standardized dataset.");
    
    const advancedContainer = document.getElementById("advanced-analytics-container");
    const advJsonBtn = document.getElementById("export-advanced-json-btn");
    if (result.advanced_fairness) {
      if (advancedContainer) advancedContainer.style.display = "block";
      if (advJsonBtn) advJsonBtn.style.display = "block";
      renderAdvancedMetricFrame(result.advanced_fairness);
      renderCustomMetricRules(result.advanced_fairness);
      bindCustomMetricEvaluator(result.advanced_fairness);
      renderIntersectional(result.advanced_fairness.intersectional);
      renderMitigations(result.advanced_fairness.mitigations);
      
      const updateAdvancedMetric = () => {
        const dropdown = document.getElementById("advanced-metric-dropdown");
        const labelEl = document.getElementById("advanced-metric-label");
        const valEl = document.getElementById("advanced-metric-value");
        const ciEl = document.getElementById("advanced-metric-ci");
        if (!dropdown || !valEl) return;
        
        const metricKey = dropdown.value;
        const metrics = result.advanced_fairness.metrics?.metrics || {};
        const ci = result.advanced_fairness.confidence_intervals || {};
        renderAdvancedMetricVisual(result.advanced_fairness, metricKey);
        
        let val = metrics[metricKey];
        if (val !== undefined) {
          valEl.textContent = formatDecimal(val, 4);
        } else {
          valEl.textContent = "-";
        }
        
        if (labelEl) {
          labelEl.textContent = ADVANCED_METRIC_LABELS[metricKey] || dropdown.options[dropdown.selectedIndex].text;
        }
        
        const ciKey = metricKey === "demographic_parity_ratio" ? "DIR" : metricKey === "demographic_parity_difference" ? "SPD" : null;
        if (ciKey && ci[ciKey]) {
          ciEl.textContent = `[ ${ci[ciKey].lower}, ${ci[ciKey].upper} ]`;
        } else {
          ciEl.textContent = "[ -, - ]";
        }
      };
      
      const dropdown = document.getElementById("advanced-metric-dropdown");
      if (dropdown) {
        dropdown.removeEventListener("change", window._updateAdvancedMetricHandler);
        window._updateAdvancedMetricHandler = updateAdvancedMetric;
        dropdown.addEventListener("change", window._updateAdvancedMetricHandler);
        updateAdvancedMetric();
      }
    } else {
      if (advancedContainer) advancedContainer.style.display = "none";
      if (advJsonBtn) advJsonBtn.style.display = "none";
    }

    persistLastResult(result);

    // Color-code DIR bar and metric values
    const dirValue = Number(result.DIR || 0);
    const dirBar = document.getElementById("dir-bar");
    const dirText = document.getElementById("dir-text");
    if (dirBar) {
      const width = Math.max(2, Math.min(100, dirValue * 100));
      dirBar.style.width = `${width}%`;
      dirBar.style.backgroundColor = dirValue < 0.5 ? "#ef4444" : dirValue < 0.8 ? "#f59e0b" : "#10b981";
    }
    if (dirText) {
      dirText.style.color = dirValue < 0.5 ? "#ef4444" : dirValue < 0.8 ? "#f59e0b" : "#10b981";
    }

    const diffValue = Number(result.difference || 0);
    const diffBar = document.getElementById("difference-bar");
    if (diffBar) {
      diffBar.style.width = `${Math.min(100, diffValue * 100)}%`;
      diffBar.style.backgroundColor = diffValue > 0.2 ? "#ef4444" : diffValue > 0.1 ? "#f59e0b" : "#10b981";
    }

    const parityValue = Number(result.stats?.parity_percent || 0) / 100;
    const parityBar = document.getElementById("parity-bar");
    if (parityBar) {
      parityBar.style.width = `${Math.min(100, parityValue * 100)}%`;
      parityBar.style.backgroundColor = parityValue < 0.5 ? "#ef4444" : parityValue < 0.8 ? "#f59e0b" : "#10b981";
    }

    const eodValue = Math.abs(Number(result.metrics?.EOD || 0));
    const eodBar = document.getElementById("eod-bar");
    if (eodBar) {
      eodBar.style.width = `${Math.min(100, eodValue * 100)}%`;
      eodBar.style.backgroundColor = eodValue > 0.2 ? "#ef4444" : eodValue > 0.1 ? "#f59e0b" : "#10b981";
    }

    const aodValue = Math.abs(Number(result.metrics?.AOD || 0));
    const aodBar = document.getElementById("aod-bar");
    if (aodBar) {
      aodBar.style.width = `${Math.min(100, aodValue * 100)}%`;
      aodBar.style.backgroundColor = aodValue > 0.2 ? "#ef4444" : aodValue > 0.1 ? "#f59e0b" : "#10b981";
    }

    requestSimulatorPreview();

    // Populate explainer chat context
    currentMetrics = {
      dir: result.DIR,
      spd: result.difference,
      eod: result.metrics ? (result.metrics.EOD ?? 0) : 0,
      aod: result.metrics ? (result.metrics.AOD ?? 0) : 0,
      bias_score: result.bias_score,
      severity: result.severity,
      most_advantaged_group: result.most_advantaged_group,
      least_advantaged_group: result.least_advantaged_group,
      recommendations: (result.recommendations || []).slice(0, 5),
      warnings: (result.warnings || []).slice(0, 5),
      hotspots: (result.bias_hotspots || []).slice(0, 3),
      feature_impact: (result.feature_impact_ranking || []).slice(0, 5),
      repair_suggestions: (result.repair_suggestions || []).slice(0, 5),
      patterns: (result.bias_pattern && result.bias_pattern.pattern_type) ? [result.bias_pattern.pattern_type] : [],
      proxies: Array.isArray(result.proxy_analysis) ? result.proxy_analysis.map(p => p.feature) : []
    };
    currentDatasetMeta = {
      name: result.file_name || "Unknown",
      protected_attr: result.protected_attribute || "Unknown",
      outcome: result.outcome_column || "Unknown"
    };
    if (!isKnownResult && !restoringSession) {
      currentAiMarkdown = "";
      clearAiAnalyzerPanels();
      explainerHistory = [];
      resetExplainerChatUi();
    }

    showExplainerPanel();
    if (!privacyModeEnabled && !sessionContainsPrivateWork && !restoringSession) {
      saveCurrentSession({ expectedSessionId: currentSessionId });
    } else {
      queueSessionSave();
    }
  }

  function renderError(message) {
    currentAnalysisResult = null;
    setText("result-mode-chip", "Error");
    setText("severity-text", "Unable To Analyze");
    setText("bias-detected-text", "The request did not complete.");
    renderExplanation(message);
    setText("dataset-meta-text", "Check your input and try again.");
    setText("bias-score-text", "0");
    setText("dir-text", "0.0000");
    setText("difference-text", "0.0000");
    setText("parity-text", "0.0%");
    setText("eod-text", "0.0000");
    setText("aod-text", "0.0000");
    setText("advantaged-group-text", "-");
    setText("disadvantaged-group-text", "-");
    setText("selection-gap-percent-text", "0%");
    setText("influential-feature-text", "-");
    setText("hidden-bias-text", "No");
    renderRecommendations([message]);

    renderEmptyState("group-bars", "No group data available for this request.");
    renderEmptyState("hotspots-list", "Hotspot analysis is unavailable for this request.");
    renderEmptyState("simulations-list", "Simulation output is unavailable for this request.");
    renderEmptyState("repairs-list", "Repair suggestions are unavailable for this request.");
    renderEmptyState("feature-impact-list", "Feature impact ranking is unavailable for this request.");
    renderEmptyState("warnings-list", "No reliability warnings available.");
    renderProxyAnalysis({ proxy_analysis: [] });
    renderDatasetRisk({});
    renderBiasPattern({});
    setExportState(false, "Run a dataset audit before exporting.");
    setText("hotspot-count-chip", "0 Hotspots");
    setText("simulation-count-chip", "0 Scenarios");
    setText("repair-count-chip", "0 Suggestions");
    setText("feature-count-chip", "0 Features");
    setText("warning-count-chip", "0 Warnings");
  }

  function renderNeutralResult(mode = "dataset") {
    currentAnalysisResult = null;
    currentMetrics = null;
    currentDatasetMeta = null;
    currentAiMarkdown = "";
    explainerHistory = [];
    resetExplainerChatUi();
    clearAiAnalyzerPanels();

    const label = mode === "model" ? "Model" : "Waiting";
    setText("result-mode-chip", label);
    setText("severity-text", "No Analysis");
    setText("bias-detected-text", "Run an audit to populate this summary.");
    renderExplanation({
      headline: mode === "model" ? "Model audit has not been run yet." : "No audit has been run yet.",
      bullets: [
        "Disparate impact ratio: 0.0000",
        "Statistical parity difference: 0.0000",
        "Equal opportunity difference: 0.0000",
        "Average odds difference: 0.0000",
      ],
      recommendation: mode === "model"
        ? "Choose test data and a model file, then run the model audit."
        : "Upload a dataset and run the dataset audit.",
    });
    setText("dataset-meta-text", mode === "model" ? "Model audit results will appear after running the model audit." : "Upload a dataset to begin.");
    setText("bias-score-text", "0.0");
    setText("dir-text", "0.0000");
    setText("difference-text", "0.0000");
    setText("parity-text", "0.0%");
    setText("eod-text", "0.0000");
    setText("aod-text", "0.0000");
    setText("advantaged-group-text", "-");
    setText("disadvantaged-group-text", "-");
    setText("selection-gap-percent-text", "0.0%");
    setText("influential-feature-text", "-");
    setText("hidden-bias-text", "No");
    renderRecommendations([]);

    renderEmptyState("group-bars", "Run an audit to compare group selection rates.");
    renderEmptyState("hotspots-list", "Hotspot analysis appears after an audit.");
    renderEmptyState("simulations-list", "Simulation output appears after an audit.");
    renderEmptyState("repairs-list", "Repair suggestions appear after an audit.");
    renderEmptyState("feature-impact-list", "Feature impact ranking appears after an audit.");
    renderEmptyState("warnings-list", "Reliability warnings appear after an audit.");
    renderProxyAnalysis({ proxy_analysis: [] });
    renderDatasetRisk({});
    renderBiasPattern({});
    setExportState(false, mode === "model" ? "Run a model audit before exporting." : "Run a dataset audit before exporting.");
    setText("hotspot-count-chip", "0 Hotspots");
    setText("simulation-count-chip", "0 Scenarios");
    setText("repair-count-chip", "0 Suggestions");
    setText("feature-count-chip", "0 Features");
    setText("warning-count-chip", "0 Warnings");

    const advancedContainer = document.getElementById("advanced-analytics-container");
    const advJsonBtn = document.getElementById("export-advanced-json-btn");
    if (advancedContainer) advancedContainer.style.display = "none";
    if (advJsonBtn) advJsonBtn.style.display = "none";

    const resetMeter = (id) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.width = "0%";
        el.style.backgroundColor = "#10b981";
      }
    };
    resetMeter("bias-score-bar");
    resetMeter("dir-bar");
    resetMeter("difference-bar");
    resetMeter("parity-bar");
    resetMeter("eod-bar");
    resetMeter("aod-bar");

    const severityText = document.getElementById("severity-text");
    if (severityText) {
      severityText.className = "mt-3 text-3xl font-black text-white";
      severityText.style.color = "";
    }

    const chip = document.getElementById("result-mode-chip");
    if (chip) {
      chip.className = "rounded-full bg-slate-200 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-600";
    }

    requestSimulatorPreview();
  }

  function clearAiAnalyzerPanels() {
    const resultPanel = document.getElementById("ai-result-panel");
    const errorPanel = document.getElementById("ai-error-panel");
    const responseText = document.getElementById("ai-response-text");
    if (resultPanel) resultPanel.classList.add("hidden");
    if (errorPanel) errorPanel.classList.add("hidden");
    if (responseText) responseText.innerHTML = "";
    setText("ai-model-name", "-");
    setText("ai-row-count", "0");
  }

  function setPrivacyMode(enabled) {
    privacyModeEnabled = Boolean(enabled);
    const chip = document.getElementById("ai-mode-chip");
    const help = document.getElementById("ai-analyzer-help-text");
    const submitBtn = document.getElementById("ai-submit-btn");
    const submitText = submitBtn ? submitBtn.querySelector("span") : null;
    const chatInput = document.getElementById("chat-input");
    const chatSubmit = document.getElementById("chat-submit-btn");

    document.querySelectorAll("[data-privacy-mode-toggle], #privacy-mode-toggle").forEach((toggle) => {
      toggle.checked = privacyModeEnabled;
    });
    if (chip) {
      chip.textContent = privacyModeEnabled ? "Privacy Mode" : "AI Powered";
      chip.className = privacyModeEnabled
        ? "rounded-full bg-teal-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-teal-800"
        : "rounded-full bg-secondary-container px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-on-secondary-container";
    }
    if (help) {
      help.textContent = privacyModeEnabled
        ? "Privacy Mode is on. The report will be generated deterministically from local fairness metrics; chat and external AI calls are disabled."
        : "The AI will generate a detailed comprehensive report by combining insights from your dataset sample and the ML statistical fairness outputs.";
    }
    if (submitText) {
      submitText.textContent = privacyModeEnabled ? "Generate Deterministic Report" : "Generate Detailed AI Report";
    }
    if (chatInput) {
      chatInput.disabled = privacyModeEnabled;
      chatInput.placeholder = privacyModeEnabled ? "Privacy Mode disables AI chat" : "e.g., Why is my DIR 0.7 a problem?";
      chatInput.classList.toggle("opacity-60", privacyModeEnabled);
      chatInput.classList.toggle("cursor-not-allowed", privacyModeEnabled);
    }
    if (chatSubmit) {
      chatSubmit.disabled = privacyModeEnabled;
      chatSubmit.classList.toggle("opacity-50", privacyModeEnabled);
      chatSubmit.classList.toggle("cursor-not-allowed", privacyModeEnabled);
    }
    if (privacyModeEnabled) {
      localStorage.removeItem(LAST_RESULT_KEY);
      currentDatasetId = null;
      currentModelDatasetId = null;
      setSessionStatus("Privacy Mode: autosave is off.");
    } else if (hasSignedInUser()) {
      setSessionStatus("Recent chats sync to your account.");
    }
    updatePrivateSaveButton();
  }

  function bindPrivacyModeToggle() {
    const toggles = document.querySelectorAll("[data-privacy-mode-toggle], #privacy-mode-toggle");
    if (!toggles.length) return;
    toggles.forEach((toggle) => {
      toggle.addEventListener("change", () => {
        setPrivacyMode(toggle.checked);
        if (privacyModeEnabled) {
          sessionContainsPrivateWork = Boolean(currentAnalysisResult || currentAiMarkdown || explainerHistory.length);
          updatePrivateSaveButton();
          appendMessage("assistant", "Privacy Mode is on. AI chat is disabled; use Generate Deterministic Report for an offline-style metrics report.");
        }
      });
    });
    setPrivacyMode(Array.from(toggles).some((toggle) => toggle.checked));
  }

  function resetExplainerChatUi() {
    const thread = document.getElementById("chat-thread");
    if (!thread) return;
    thread.innerHTML = "";
    const intro = document.createElement("div");
    intro.className = "max-w-[85%] self-start rounded-xl border border-slate-100 bg-white p-3 text-sm leading-relaxed text-slate-700 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300";
    intro.textContent = "Hi! I'm your AI fairness assistant. Ask me anything about the metrics computed above, their interpretation, or how to remediate the detected bias.";
    thread.appendChild(intro);
  }

  function restoreExplainerChat(history) {
    const thread = document.getElementById("chat-thread");
    if (!thread) return;
    resetExplainerChatUi();
    (history || []).forEach((message) => {
      if (!message || !message.content) return;
      appendMessage(message.role === "user" ? "user" : "assistant", message.content);
    });
  }

  function restoreSessionState(session) {
    const state = session?.workspace_state || {};
    restoringSession = true;
    try {
      datasetAnalysisResult = state.dataset_result || null;
      modelAnalysisResult = state.model_result || null;
      currentDatasetMeta = session?.dataset_meta || null;
      currentSessionId = session?.id || null;
      currentDatasetId = null;
      currentModelDatasetId = null;
      currentAiMarkdown = state.current_ai_markdown || session?.ai_report_markdown || "";
      explainerHistory = state.explainer_history || session?.ai_chat || [];
      clearAiAnalyzerPanels();

      const active = session?.audit_result || state.active_result || datasetAnalysisResult || modelAnalysisResult;
      if (active?.mode === "model") {
        modelAnalysisResult = active;
      } else if (active) {
        datasetAnalysisResult = active;
      }
      if (active) {
        renderResult(active);
      } else {
        renderNeutralResult("dataset");
        if (currentDatasetMeta?.name) {
          setText("file-name-display", currentDatasetMeta.name);
        }
      }

      explainerHistory = state.explainer_history || session?.ai_chat || [];
      restoreExplainerChat(explainerHistory);

      if (currentAiMarkdown) {
        const resultPanel = document.getElementById("ai-result-panel");
        const responseText = document.getElementById("ai-response-text");
        if (responseText) responseText.innerHTML = marked.parse(currentAiMarkdown);
        if (resultPanel) resultPanel.classList.remove("hidden");
        setText("ai-model-name", session.ai_report_source || "Saved Report");
        setText("ai-row-count", session.dataset_meta?.row_count || session.summary?.row_count || "0");
      }

      setPrivacyMode(false);
      sessionContainsPrivateWork = false;
      updatePrivateSaveButton();
      renderRecentSessions();
      setSessionStatus("Loaded saved chat.");
    } finally {
      restoringSession = false;
    }
  }

  async function loadSession(sessionId) {
    if (!sessionId || privacyModeEnabled) {
      if (privacyModeEnabled) {
        setSessionStatus("Turn off Privacy Mode before loading saved chats.");
      }
      return;
    }
    try {
      if (sessionId !== currentSessionId) {
        await flushSessionSave();
      }
      const response = await authFetch(`/api/auth/sessions/${encodeURIComponent(sessionId)}`);
      const payload = await parseErrorResponse(response, "Unable to load saved chat.");
      restoreSessionState(payload.session);
    } catch (error) {
      setSessionStatus(error.message || "Unable to load saved chat.");
    }
  }

  function clearWorkbenchForms() {
    document.getElementById("dataset-analysis-form")?.reset();
    document.getElementById("model-audit-form")?.reset();
    setText("file-name-display", "No file selected");
    setText("model-test-file-name-display", "No test data selected");
    const protectedSelect = document.getElementById("protected-attribute-input");
    const outcomeSelect = document.getElementById("outcome-column-input");
    const qualSelect = document.getElementById("qualification-column-input");
    const modelProtected = document.getElementById("model-protected-attribute-input");
    const modelLabel = document.getElementById("model-true-label-column-input");
    const modelQual = document.getElementById("model-qualification-column-input");
    if (protectedSelect) protectedSelect.innerHTML = '<option value="">Auto-detect</option>';
    if (outcomeSelect) outcomeSelect.innerHTML = '<option value="">Auto-detect</option>';
    if (qualSelect) qualSelect.innerHTML = '<option value="">Auto-detect (Recommended)</option>';
    if (modelProtected) modelProtected.innerHTML = '<option value="">Scan test data first</option>';
    if (modelLabel) modelLabel.innerHTML = '<option value="">Scan test data first</option>';
    if (modelQual) modelQual.innerHTML = '<option value="">Optional</option>';
  }

  async function startNewChat() {
    if (sessionContainsPrivateWork && !confirm("This private work has not been saved. Start a new chat and discard it?")) {
      return;
    }
    await flushSessionSave();
    currentSessionId = null;
    currentAnalysisResult = null;
    datasetAnalysisResult = null;
    modelAnalysisResult = null;
    currentDatasetId = null;
    currentModelDatasetId = null;
    currentMetrics = null;
    currentDatasetMeta = null;
    currentAiMarkdown = "";
    explainerHistory = [];
    sessionContainsPrivateWork = false;
    window.lastUploadedDatasetFile = null;
    localStorage.removeItem(LAST_RESULT_KEY);
    clearWorkbenchForms();
    clearAiAnalyzerPanels();
    setAuditFlipMode("dataset");
    renderNeutralResult("dataset");
    setPrivacyMode(privacyModeEnabled);
    renderRecentSessions();
    setSessionStatus(privacyModeEnabled ? "Privacy Mode: new private chat." : "New chat ready.");
    if (!privacyModeEnabled && hasSignedInUser()) {
      const draft = await saveCurrentSession({ allowEmpty: true, title: "New chat" });
      if (draft) {
        setSessionStatus("New chat created.");
      }
    }
  }

  async function savePrivateWork() {
    if (!sessionContainsPrivateWork && !privacyModeEnabled) return;
    const ok = confirm(
      "Save this private work to Recent Chats? This saves audit metrics, explanations, deterministic reports, chat text, and metadata to your account. Raw uploaded files are not saved.",
    );
    if (!ok) return;
    setPrivacyMode(false);
    await saveCurrentSession({ force: true, privacyModeSaved: true });
  }

  function bindSessionControls() {
    document.querySelectorAll("[data-new-chat-button], #new-chat-btn").forEach((btn) => {
      btn.addEventListener("click", startNewChat);
    });
    document.querySelectorAll("[data-save-private-session], #save-private-session-btn").forEach((btn) => {
      btn.addEventListener("click", savePrivateWork);
    });
    document.addEventListener("baised:auth-changed", loadRecentSessions);
    window.setTimeout(loadRecentSessions, 500);
  }

  function bindSidebarToggle() {
    const toggleBtn = document.getElementById("sidebar-toggle");
    if (!toggleBtn) return;

    // Restore state from localStorage on load
    const collapsed = localStorage.getItem("baised:sidebar_collapsed") === "true";
    if (collapsed) {
      document.body.classList.add("sidebar-collapsed");
      const icon = document.getElementById("sidebar-toggle-icon");
      if (icon) icon.textContent = "chevron_right";
    }

    toggleBtn.addEventListener("click", () => {
      const isCollapsed = document.body.classList.toggle("sidebar-collapsed");
      localStorage.setItem("baised:sidebar_collapsed", isCollapsed);
      const icon = document.getElementById("sidebar-toggle-icon");
      if (icon) {
        icon.textContent = isCollapsed ? "chevron_right" : "chevron_left";
      }
    });
  }

  async function requestSimulatorPreview() {
    let currentScenario = typeof window._getCurrentScenario === "function" ? window._getCurrentScenario() : "diversity_weight";
    
    const slider = document.getElementById("simulator-diversity-weight");
    const constraintText = document.getElementById("simulator-constraint-text");
    
    const diversityWeight = slider ? parseFloat(slider.value) : 0.75;
    const constraint = constraintText ? constraintText.textContent : "Optimal";

    try {
      const preview = await postJson("/simulate", {
        scenario_type: currentScenario,
        diversity_weight: diversityWeight,
        fairness_constraint: constraint,
        analysis_result: currentAnalysisResult,
      });

      if (preview.error) {
        return;
      }

      setText("simulator-instant-label", preview.instant_label || "Instant");
      setText("simulator-change-text", preview.change || "-");
      
      // Update Baseline metrics
      setText("simulator-dir-baseline", formatDecimal(preview.metrics?.baseline_DIR || 0, 4));
      setText("simulator-spd-baseline", formatDecimal(preview.metrics?.baseline_SPD || 0, 4));
      setText("simulator-score-baseline", formatDecimal(preview.metrics?.baseline_bias_score || 0, 1));
      setText("simulator-severity-baseline", preview.metrics?.baseline_severity || "LOW");

      // Update New metrics
      setText("simulator-dir-text", formatDecimal(preview.metrics?.new_DIR || 0, 4));
      setText("simulator-spd-text", formatDecimal(preview.metrics?.new_SPD || 0, 4));
      setText("simulator-score-text", formatDecimal(preview.metrics?.new_bias_score || 0, 1));
      setText("simulator-severity-text", preview.metrics?.new_severity || "LOW");

      setText("simulator-accuracy-text", formatPercent(preview.metrics?.estimated_accuracy || 0));
      setText("simulator-improvement-text", formatSignedPercent(preview.metrics?.parity_improvement_percent || 0));

      const improvementBar = document.getElementById("simulator-improvement-bar");
      if (improvementBar) {
        const rawImprovement = Number(preview.metrics?.parity_improvement_percent || 0);
        const normalizedPercent = Math.abs(rawImprovement) <= 1
          ? Math.abs(rawImprovement) * 100
          : Math.abs(rawImprovement);
        const width = Math.max(0, Math.min(100, normalizedPercent));
        improvementBar.style.width = `${width}%`;
      }
    } catch (e) {
      console.warn("Preview failed", e);
    }
  }

  function renderExplanation(explanation) {
    const container = document.getElementById("explanation-container");
    if (!container) return;

    if (!explanation) {
      container.innerHTML = `<p class="text-sm italic text-slate-500 dark:text-zinc-400">Explanation data not available.</p>`;
      return;
    }

    if (typeof explanation === 'string') {
      container.innerHTML = `<p class="text-sm leading-7 text-slate-700 dark:text-zinc-200">${explanation}</p>`;
      return;
    }

    const bulletsHtml = (explanation.bullets || [])
      .map(b => `<li class="ml-4 list-disc text-sm text-slate-700 dark:text-zinc-200">${b}</li>`)
      .join("");

    container.innerHTML = `
      <p class="font-semibold text-indigo-900 dark:text-teal-200 mb-2">${explanation.headline || ""}</p>
      <ul class="space-y-1 mb-3">
        ${bulletsHtml}
      </ul>
      <div class="mt-3 rounded-lg border border-indigo-200 bg-indigo-100/50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
        <p class="text-[10px] font-bold uppercase tracking-widest text-indigo-800 dark:text-zinc-300 mb-1">Recommended Fix</p>
        <p class="text-sm font-medium text-indigo-900 dark:text-zinc-100">${explanation.fix || "None"}</p>
      </div>
    `;
  }

  function aiReportJsonToMarkdown(report) {
    const actions = Array.isArray(report.recommended_actions) ? report.recommended_actions : [];
    const flags = Array.isArray(report.compliance_flags) ? report.compliance_flags : [];
    const root = report.root_cause || {};
    const groups = report.group_comparison || {};
    
    // New schema fields
    const proxyRisks = Array.isArray(report.proxy_risks) ? report.proxy_risks : [];
    const compRisks = Array.isArray(report.compliance_risks) ? report.compliance_risks : flags;
    const mitigationPlan = Array.isArray(report.mitigation_plan) ? report.mitigation_plan : actions;

    const actionLines = mitigationPlan
      .map((item) => `> - **${item.priority || "ACTION"}**: ${item.action || ""}`)
      .join("\n");
    const flagLines = compRisks.map((item) => `- ${item}`).join("\n");
    
    const proxyLines = proxyRisks.map((item) => `- **${item.feature}** (${item.risk}): ${item.explanation}`).join("\n");

    return [
      "### Executive Summary",
      `**${report.severity_label || "LOW"} Bias** - ${report.headline || "No headline generated."}`,
      "",
      report.executive_summary || report.metrics_summary || "Metric summary unavailable.",
      "",
      "### Technical Audit",
      report.technical_audit || `**DIR**=${report.DIR || "-"}, **SPD**=${report.SPD || "-"}`,
      "",
      "### Bias Pattern",
      `**Detected Pattern:** ${report.pattern_detected || "None"}`,
      "",
      "### Root Cause",
      `**Primary Driver:** ${root.primary_driver || "-"}`,
      "",
      root.explanation || "Root-cause explanation unavailable.",
      "",
      "### Group Comparison",
      `Most advantaged: **${groups.most_advantaged || "-"}**`,
      `Least advantaged: **${groups.least_advantaged || "-"}**`,
      `Disparity ratio: **${groups.disparity_ratio || "-"}**`,
      "",
      groups.plain_english || "",
      "",
      "### Proxy Risks",
      proxyLines || "- No significant proxy risks detected.",
      "",
      "### Mitigation Plan",
      actionLines || "> - No actions returned.",
      "",
      "### Compliance Risks",
      flagLines || "- No compliance flags returned.",
      "",
      `### Confidence`,
      `**${report.confidence || "LOW"}** - ${report.confidence_reason || "No confidence rationale returned."}`,
      report.confidence_notes ? `*${report.confidence_notes}*` : ""
    ].filter(line => line !== null).join("\n");
  }

  function normalizeAiProseMarkdown(text) {
    const source = String(text || "").replace(/\r\n/g, "\n").trim();
    if (!source) return "";

    const lines = source.split("\n");
    const blocks = [];
    let paragraph = [];

    const flushParagraph = () => {
      if (!paragraph.length) return;
      blocks.push(paragraph.join(" "));
      paragraph = [];
    };

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        flushParagraph();
        continue;
      }

      const isHeading = /^#{1,6}\s+/.test(line);
      const isList = /^([-*+]|>\s|(\d+\.))\s+/.test(line) || /^>\s?/.test(line);
      const isFence = /^```/.test(line);

      if (isHeading || isList || isFence) {
        flushParagraph();
        blocks.push(rawLine.replace(/\s+$/g, ""));
        continue;
      }

      paragraph.push(line);
    }

    flushParagraph();
    return blocks.join("\n\n");
  }

  function bindSimulator() {
    const buttons = Array.from(document.querySelectorAll("[data-scenario]"));
    if (!buttons.length) return;

    let currentScenario = "threshold";

    const applyScenarioState = (selected) => {
      currentScenario = selected;
      buttons.forEach((button) => {
        const active = button.dataset.scenario === selected;
        if (active) {
          button.className = "w-full rounded-xl border border-secondary bg-secondary/10 px-4 py-3 text-left text-sm font-semibold text-secondary transition";
        } else {
          button.className = "w-full rounded-xl border border-outline-variant bg-white px-4 py-3 text-left text-sm font-medium text-slate-700 transition hover:bg-surface-container-low dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700";
        }
      });
    };

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const selected = button.dataset.scenario || "threshold";
        applyScenarioState(selected);
        requestSimulatorPreview();
      });
    });

    applyScenarioState("threshold");
    
    // Make requestSimulatorPreview use currentScenario
    window._getCurrentScenario = () => currentScenario;
    requestSimulatorPreview();
  }

  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }

  function describeRequestError(error) {
    if (error?.name === "AbortError") {
      return "The request timed out. Please try again with a smaller file or restart the backend.";
    }
    if (error instanceof TypeError && /fetch/i.test(error.message || "")) {
      return `Could not reach the bAIsed backend at ${API_BASE || window.location.origin}. Start Flask with \`python run.py\` and open http://127.0.0.1:5000/workbench.`;
    }
    return error?.message || String(error);
  }

  async function parseApiResponse(response) {
    const text = await response.text();
    const trimmed = text.trim();
    const contentType = (response.headers.get("content-type") || "").toLowerCase();

    if (!trimmed) {
      throw new Error("Server returned an empty response.");
    }

    const looksLikeHtml =
      trimmed.startsWith("<!doctype") ||
      trimmed.startsWith("<!DOCTYPE") ||
      trimmed.startsWith("<html") ||
      trimmed.startsWith("<HTML");

    if (looksLikeHtml || (!contentType.includes("json") && trimmed.startsWith("<"))) {
      throw new Error(
        "Server returned HTML instead of JSON. Start the Flask backend with `python run.py` and open http://127.0.0.1:5000/workbench."
      );
    }

    try {
      return JSON.parse(trimmed);
    } catch (parseError) {
      throw new Error(`Invalid JSON response: ${trimmed.slice(0, 200)}`);
    }
  }

  function compactAnalysisPayload(result) {
    if (!result || typeof result !== "object") {
      return {};
    }

    const metrics = result.metrics || {};
    return {
      severity: result.severity,
      DIR: result.DIR ?? metrics.DIR,
      difference: result.difference,
      SPD: metrics.SPD,
      EOD: metrics.EOD,
      AOD: metrics.AOD,
      bias_score: result.bias_score,
      most_advantaged_group: result.most_advantaged_group,
      least_advantaged_group: result.least_advantaged_group,
      most_influential_feature: result.most_influential_feature,
      warnings: (result.warnings || []).slice(0, 5),
      recommendations: (result.recommendations || []).slice(0, 5),
      bias_hotspots: (result.bias_hotspots || []).slice(0, 3),
      feature_impact_ranking: (result.feature_impact_ranking || []).slice(0, 5),
      proxy_analysis: (result.proxy_analysis || []).slice(0, 5),
      dataset_risk: result.dataset_risk || {},
      bias_pattern: result.bias_pattern || {},
      mode: result.mode,
      row_count: result.row_count,
      protected_attribute: result.protected_attribute,
      outcome_column: result.outcome_column,
    };
  }

  async function postJson(url, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000); // 60 second timeout
    try {
      const response = await fetch(apiUrl(url), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      const data = await parseApiResponse(response);
      if (!response.ok) {
        console.error(`HTTP ${response.status}:`, data);
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function postForm(url, formData, options = {}) {
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs || 90000; // AI analysis may call Gemini
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(apiUrl(url), {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      const data = await parseApiResponse(response);
      if (!response.ok) {
        console.error(`HTTP ${response.status}:`, data);
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  function bindSimpleForm() {
    const form = document.getElementById("simple-analysis-form");
    const reset = document.getElementById("simple-reset");
    if (!form || !reset) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn?.textContent;
      
      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Analyzing...";
        }

        const result = await triggerPuppyDelay(() => postJson("/analyze", {
          groupA: document.getElementById("group-a-input").value,
          groupB: document.getElementById("group-b-input").value,
        }));

        if (result.error) {
          renderError(result.error);
          return;
        }

        renderResult(result);
      } catch (error) {
        console.error("Analysis error:", error);
        const errorMsg = error.name === "AbortError" 
          ? "Analysis timed out. Please try again."
          : `Analysis failed: ${error.message || error}`;
        renderError(errorMsg);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    });

    reset.addEventListener("click", () => {
      form.reset();
    });
  }

  function bindScanOnSelect() {
    const fileInput = document.getElementById("dataset-file-input");
    if (!fileInput) return;

    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      const scanRequestId = ++datasetScanRequestId;
      currentDatasetId = null;
      currentAnalysisResult = null;
      datasetAnalysisResult = null;
      currentMetrics = null;
      currentDatasetMeta = null;
      window.lastUploadedDatasetFile = null;
      renderNeutralResult("dataset");

      const formData = new FormData();
      formData.append("file", file);
      if (privacyModeEnabled) {
        formData.append("privacy_mode", "true");
      }

      try {
        console.log("Starting scan for file:", file.name);
        // Show scanning state in the UI
        document.getElementById('file-name-display').textContent = `Scanning ${file.name}...`;
        
        // Disable and show loading in dropdowns
        const selects = ["protected-attribute-input", "outcome-column-input", "qualification-column-input"];
        selects.forEach(id => {
          const el = document.getElementById(id);
          if (el) {
            el.disabled = true;
            el.innerHTML = '<option value="">Scanning columns...</option>';
          }
        });

        let scanResult;
        try {
          scanResult = await postForm("/scan", formData);
        } finally {
          if (scanRequestId !== datasetScanRequestId) {
            return;
          }
          selects.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = false;
                // If it's still stuck on "Scanning...", reset it to "Auto-detect"
                if (el.innerHTML.includes("Scanning columns...")) {
                    el.innerHTML = '<option value="">Auto-detect</option>';
                }
            }
          });
        }

        console.log("Scan result received:", scanResult);
        if (scanRequestId !== datasetScanRequestId) {
          return;
        }
        
        if (!scanResult || scanResult.error) {
          console.error("Scan API error:", scanResult?.error);
          renderError(scanResult?.error || "Empty response from server");
          return;
        }
        
        if (!scanResult.columns || scanResult.columns.length === 0) {
           throw new Error("No columns detected in the file.");
        }

        currentDatasetId = scanResult.dataset_id || null;
        
        // Populate dropdowns with intelligence
        populateDropdowns(scanResult.columns, scanResult.profile);
        console.log("Dropdowns populated with", scanResult.columns.length, "columns.");
        
        // Show field analysis immediately
        renderFieldAnalysis({ stats: { column_profile: scanResult.profile } });
        
        // Update UI state
        document.getElementById('file-drop-zone').classList.add('border-secondary','bg-secondary/10');
        document.getElementById('file-drop-zone').classList.remove('border-secondary/40','bg-secondary/5');
        document.getElementById('file-name-display').textContent = file.name;
        currentDatasetMeta = {
          name: file.name,
          protected_attr: document.getElementById("protected-attribute-input")?.value || "",
          outcome: document.getElementById("outcome-column-input")?.value || "",
          row_count: scanResult.row_count || scanResult.profile?.row_count || null,
        };
        
        window.lastUploadedDatasetFile = file;

      } catch (err) {
        if (scanRequestId !== datasetScanRequestId) {
          return;
        }
        console.error("Scan error:", err);
        renderError(describeRequestError(err) || "Failed to scan dataset schema.");
      }
    });
  }

  function bindDragAndDrop() {
    const dropZone = document.getElementById("file-drop-zone");
    const fileInput = document.getElementById("dataset-file-input");
    if (!dropZone || !fileInput) return;

    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.add("border-secondary", "bg-secondary/10");
        dropZone.classList.remove("border-secondary/40", "bg-secondary/5");
      }, false);
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => {
        // Only remove if it's not the currently selected file state
        if (!fileInput.files || fileInput.files.length === 0) {
          dropZone.classList.remove("border-secondary", "bg-secondary/10");
          dropZone.classList.add("border-secondary/40", "bg-secondary/5");
        }
      }, false);
    });

    dropZone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        fileInput.files = files;
        // Trigger the change event manually since setting .files doesn't trigger it
        fileInput.dispatchEvent(new Event("change"));
      }
    }, false);
  }

  function populateDropdowns(columns, profile = {}) {
    const protectedSelect = document.getElementById("protected-attribute-input");
    const outcomeSelect = document.getElementById("outcome-column-input");
    const qualSelect = document.getElementById("qualification-column-input");

    if (!protectedSelect || !outcomeSelect || !qualSelect) return;

    protectedSelect.innerHTML = '<option value="">Auto-detect</option>';
    outcomeSelect.innerHTML = '<option value="">Auto-detect</option>';
    qualSelect.innerHTML = '<option value="">Auto-detect (Recommended)</option>';

    let bestProtected = { name: "", score: -1 };
    let bestOutcome = { name: "", score: -1 };

    columns.forEach(col => {
      const p = profile[col] || {};
      
      // Track best guesses
      if (p.group_score > bestProtected.score) {
        bestProtected = { name: col, score: p.group_score };
      }
      if (p.outcome_score > bestOutcome.score) {
        bestOutcome = { name: col, score: p.outcome_score };
      }

      protectedSelect.add(new Option(col, col));
      outcomeSelect.add(new Option(col, col));
      qualSelect.add(new Option(col, col));
    });

    // Pre-select if a strong candidate is found (threshold to avoid noise)
    if (bestProtected.score > 2.0) {
      protectedSelect.value = bestProtected.name;
    }
    if (bestOutcome.score > 3.0) {
      outcomeSelect.value = bestOutcome.name;
    }
  }

  function populateModelDropdowns(columns, profile = {}) {
    const protectedSelect = document.getElementById("model-protected-attribute-input");
    const trueLabelSelect = document.getElementById("model-true-label-column-input");
    const qualSelect = document.getElementById("model-qualification-column-input");
    if (!protectedSelect || !trueLabelSelect || !qualSelect) return;

    protectedSelect.innerHTML = '<option value="">Select protected attribute</option>';
    trueLabelSelect.innerHTML = '<option value="">Select true label</option>';
    qualSelect.innerHTML = '<option value="">Optional</option>';

    let bestProtected = { name: "", score: -1 };
    let bestOutcome = { name: "", score: -1 };

    columns.forEach((col) => {
      const p = profile[col] || {};
      if (p.group_score > bestProtected.score) {
        bestProtected = { name: col, score: p.group_score };
      }
      if (p.outcome_score > bestOutcome.score) {
        bestOutcome = { name: col, score: p.outcome_score };
      }
      protectedSelect.add(new Option(col, col));
      trueLabelSelect.add(new Option(col, col));
      qualSelect.add(new Option(col, col));
    });

    if (bestProtected.name) {
      protectedSelect.value = bestProtected.name;
    }
    if (bestOutcome.name) {
      trueLabelSelect.value = bestOutcome.name;
    }
    if (protectedSelect.value && trueLabelSelect.value === protectedSelect.value) {
      const alternateOutcome = columns.find((col) => col !== protectedSelect.value);
      if (alternateOutcome) {
        trueLabelSelect.value = alternateOutcome;
      }
    }
  }

  function setAuditFlipMode(mode) {
    const card = document.getElementById("audit-flip-card");
    if (!card) return;
    card.classList.add("is-flipping");
    card.classList.toggle("is-model", mode === "model");
    window.setTimeout(() => {
      card.classList.remove("is-flipping");
    }, 580);
  }

  function switchAuditMode(mode) {
    setAuditFlipMode(mode);
    if (mode === "dataset") {
      if (datasetAnalysisResult) {
        renderResult(datasetAnalysisResult);
      } else {
        renderNeutralResult("dataset");
      }
      return;
    }

    if (modelAnalysisResult) {
      renderResult(modelAnalysisResult);
    } else {
      renderNeutralResult("model");
    }
  }

  function bindAuditFlipControls() {
    const showModelBtn = document.getElementById("show-model-audit");
    const showDatasetBtn = document.getElementById("show-dataset-audit");
    if (showModelBtn) {
      showModelBtn.addEventListener("click", () => switchAuditMode("model"));
    }
    if (showDatasetBtn) {
      showDatasetBtn.addEventListener("click", () => switchAuditMode("dataset"));
    }
  }

  function bindDatasetForm() {
    const form = document.getElementById("dataset-analysis-form");
    const reset = document.getElementById("dataset-reset");
    if (!form || !reset) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fileInput = document.getElementById("dataset-file-input");
      const file = fileInput.files && fileInput.files[0];
      if (!file) {
        renderError("Please choose a CSV or XLSX file before uploading.");
        return;
      }
      
      window.lastUploadedDatasetFile = file;

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn?.textContent;

      const formData = new FormData();
      if (currentDatasetId) {
        formData.append("dataset_id", currentDatasetId);
      } else {
        formData.append("file", file);
      }
      if (privacyModeEnabled) {
        formData.append("privacy_mode", "true");
      }

      const protectedAttribute = document.getElementById("protected-attribute-input").value;
      const outcomeColumn = document.getElementById("outcome-column-input").value;
      const qualificationColumn = document.getElementById("qualification-column-input").value;

      if (protectedAttribute) {
        formData.append("protected_attribute", protectedAttribute);
      }

      if (outcomeColumn) {
        formData.append("outcome_column", outcomeColumn);
      }

      if (qualificationColumn) {
        formData.append("qualification_column", qualificationColumn);
      }

      const advancedModeToggle = document.getElementById("advanced-mode-toggle");
      if (advancedModeToggle && advancedModeToggle.checked) {
        formData.append("advanced_mode", "true");
      }

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Uploading & Analyzing...";
        }

        const result = await triggerPuppyDelay(() => postForm("/upload", formData));
        if (result.error) {
          renderError(result.error);
          return;
        }

        renderResult(result);
      } catch (error) {
        console.error("Upload error:", error);
        const errorMsg = error.name === "AbortError" 
          ? "Upload timed out. Please try again with a smaller file."
          : `Upload failed: ${describeRequestError(error)}`;
        renderError(errorMsg);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    });

    reset.addEventListener("click", () => {
      form.reset();
      datasetScanRequestId++;
      
      // Reset file display
      const fileNameDisplay = document.getElementById('file-name-display');
      if (fileNameDisplay) fileNameDisplay.textContent = "No file selected";
      
      const dropZone = document.getElementById('file-drop-zone');
      if (dropZone) {
        dropZone.classList.remove('border-secondary', 'bg-secondary/10');
        dropZone.classList.add('border-secondary/40', 'bg-secondary/5');
      }

      // Reset internal state
      currentDatasetId = null;
      currentAnalysisResult = null;
      datasetAnalysisResult = null;
      window.lastUploadedDatasetFile = null;
      renderNeutralResult("dataset");

      // Also reset selects
      document.getElementById("protected-attribute-input").innerHTML = '<option value="">Auto-detect</option>';
      document.getElementById("outcome-column-input").innerHTML = '<option value="">Auto-detect</option>';
      document.getElementById("qualification-column-input").innerHTML = '<option value="">Auto-detect (Recommended)</option>';
    });
  }

  function bindModelAuditForm() {
    const form = document.getElementById("model-audit-form");
    const reset = document.getElementById("model-audit-reset");
    const testInput = document.getElementById("model-test-file-input");
    if (!form || !reset || !testInput) return;

    async function scanSelectedModelTestData() {
      const file = testInput.files && testInput.files[0];
      const display = document.getElementById("model-test-file-name-display");
      currentModelDatasetId = null;
      if (!file) {
        if (display) display.textContent = "No test data selected";
        return null;
      }
      if (display) display.textContent = `Scanning ${file.name}...`;

      const formData = new FormData();
      formData.append("file", file);
      if (privacyModeEnabled) {
        formData.append("privacy_mode", "true");
      }
      try {
        const scanResult = await postForm("/scan", formData);
        if (scanResult.error) {
          renderError(scanResult.error);
          return;
        }
        currentModelDatasetId = scanResult.dataset_id || null;
        populateModelDropdowns(scanResult.columns || [], scanResult.profile || {});
        if (display) display.textContent = file.name;
        return scanResult;
      } catch (error) {
        console.error("Model test data scan error:", error);
        renderError(describeRequestError(error) || "Failed to scan model test data.");
        if (display) display.textContent = "Scan failed";
        return null;
      }
    }

    testInput.addEventListener("change", scanSelectedModelTestData);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const testFile = testInput.files && testInput.files[0];
      const modelFileInput = document.getElementById("model-file-input");
      const modelFile = modelFileInput?.files && modelFileInput.files[0];

      if (!testFile && !currentModelDatasetId) {
        renderError("Please choose a CSV or XLSX test dataset for the model audit.");
        return;
      }
      if (!modelFile) {
        renderError("Please choose a .pkl, .joblib, or TensorFlow/Keras model file.");
        return;
      }

      const protectedSelect = document.getElementById("model-protected-attribute-input");
      const trueLabelSelect = document.getElementById("model-true-label-column-input");
      const needsScan =
        !currentModelDatasetId ||
        !protectedSelect ||
        !trueLabelSelect ||
        protectedSelect.options.length <= 1 ||
        trueLabelSelect.options.length <= 1;
      if (needsScan) {
        const scanResult = await scanSelectedModelTestData();
        if (!scanResult) {
          renderError("Could not scan the test dataset. Please reselect the CSV/XLSX file and try again.");
          return;
        }
      }

      const protectedAttribute = document.getElementById("model-protected-attribute-input")?.value || "";
      const trueLabelColumn = document.getElementById("model-true-label-column-input")?.value || "";
      const qualificationColumn = document.getElementById("model-qualification-column-input")?.value || "";

      if (!protectedAttribute) {
        renderError("Please select the protected attribute column for the model audit.");
        return;
      }
      if (!trueLabelColumn) {
        renderError("Please select the true label column for the model audit.");
        return;
      }

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn?.textContent;
      const formData = new FormData();
      if (currentModelDatasetId) {
        formData.append("dataset_id", currentModelDatasetId);
      } else {
        formData.append("file", testFile);
      }
      if (privacyModeEnabled) {
        formData.append("privacy_mode", "true");
      }
      formData.append("model_file", modelFile);
      formData.append("protected_attribute", protectedAttribute);
      formData.append("true_label_column", trueLabelColumn);
      if (qualificationColumn) {
        formData.append("qualification_column", qualificationColumn);
      }

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Running Model Audit...";
        }
        const result = await triggerPuppyDelay(() => postForm("/model-upload", formData, { timeoutMs: 180000 }));
        if (result.error) {
          renderError(result.error);
          return;
        }
        renderResult(result);
      } catch (error) {
        console.error("Model audit error:", error);
        const errorMsg = error.name === "AbortError"
          ? "Model audit timed out. Please try a smaller test dataset."
          : `Model audit failed: ${describeRequestError(error)}`;
        renderError(errorMsg);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    });

    reset.addEventListener("click", () => {
      form.reset();
      currentModelDatasetId = null;
      modelAnalysisResult = null;
      const display = document.getElementById("model-test-file-name-display");
      if (display) display.textContent = "No test data selected";
      const protectedSelect = document.getElementById("model-protected-attribute-input");
      const trueLabelSelect = document.getElementById("model-true-label-column-input");
      const qualSelect = document.getElementById("model-qualification-column-input");
      if (protectedSelect) protectedSelect.innerHTML = '<option value="">Scan test data first</option>';
      if (trueLabelSelect) trueLabelSelect.innerHTML = '<option value="">Scan test data first</option>';
      if (qualSelect) qualSelect.innerHTML = '<option value="">Optional</option>';
      renderNeutralResult("model");
    });
  }

  function bindAiAnalyzerForm() {
    const form = document.getElementById("ai-analyzer-form");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      
      const resultPanel = document.getElementById("ai-result-panel");
      const errorPanel = document.getElementById("ai-error-panel");
      const submitBtn = document.getElementById("ai-submit-btn");
      const submitText = submitBtn ? submitBtn.querySelector("span") : null;
      const spinner = document.getElementById("ai-spinner");
      
      const file = window.lastUploadedDatasetFile;

      currentAiMarkdown = "";
      clearAiAnalyzerPanels();

      if (((!file && !currentDatasetId) && !privacyModeEnabled) || !currentAnalysisResult) {
        document.getElementById("ai-error-text").textContent = "Please upload a dataset and run the Dataset Audit first.";
        errorPanel.classList.remove("hidden");
        return;
      }
      
      if (submitBtn) submitBtn.disabled = true;
      if (submitText) submitText.textContent = "Analyzing...";
      if (spinner) {
        spinner.classList.remove("hidden");
        spinner.classList.add("animate-spin");
      }
      
      const formData = new FormData();
      if (currentDatasetId) {
        formData.append("dataset_id", currentDatasetId);
      } else if (file) {
        formData.append("file", file);
      }
      formData.append("analysis_json", JSON.stringify(compactAnalysisPayload(currentAnalysisResult)));
      if (privacyModeEnabled) {
        formData.append("privacy_mode", "true");
      }
      
      try {
        const result = await triggerPuppyDelay(() => postForm("/ai-analyze", formData));
        
        if (result.error) {
          document.getElementById("ai-error-text").textContent = result.error;
          errorPanel.classList.remove("hidden");
        } else {
          const isStructured = result && typeof result === "object" && result.severity_label && result.root_cause;
          if (isStructured) {
            currentAiMarkdown = aiReportJsonToMarkdown(result);
            if (result._warning) {
              currentAiMarkdown = `> **Note:** ${result._warning}\n\n${currentAiMarkdown}`;
            }
            document.getElementById("ai-model-name").textContent = result._source || "AI Engine";
            document.getElementById("ai-row-count").textContent = result._row_count || "0";
          } else {
            currentAiMarkdown = normalizeAiProseMarkdown(result.ai_response || "");
            document.getElementById("ai-model-name").textContent = result.model || "Unknown Model";
            document.getElementById("ai-row-count").textContent = result.row_count || "0";
          }
          document.getElementById("ai-response-text").innerHTML = marked.parse(currentAiMarkdown);
          resultPanel.classList.remove("hidden");
          queueSessionSave();
        }
      } catch (error) {
        document.getElementById("ai-error-text").textContent = describeRequestError(error);
        errorPanel.classList.remove("hidden");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = privacyModeEnabled ? "Generate Deterministic Report" : "Generate Detailed AI Report";
        if (spinner) {
          spinner.classList.add("hidden");
          spinner.classList.remove("animate-spin");
        }
      }
    });
  }

  function bindExportButtons() {
    const colabBtn = document.getElementById("export-colab-btn");
    const whatIfBtn = document.getElementById("export-what-if-btn");
    setExportState(false);

    if (colabBtn) {
      colabBtn.addEventListener("click", () => {
        const url = buildExportUrl("colab");
        if (currentDatasetId && currentAnalysisResult) {
          window.location.href = url;
        } else {
          setExportState(false, "Run a dataset audit before exporting.");
        }
      });
    }

    if (whatIfBtn) {
      whatIfBtn.addEventListener("click", () => {
        const url = buildExportUrl("what-if");
        if (currentDatasetId && currentAnalysisResult) {
          window.location.href = url;
        } else {
          setExportState(false, "Run a dataset audit before exporting.");
        }
      });
    }

    const advJsonBtn = document.getElementById("export-advanced-json-btn");
    if (advJsonBtn) {
      advJsonBtn.addEventListener("click", () => {
        const url = buildExportUrl("advanced-json");
        if (currentDatasetId && currentAnalysisResult) {
          window.location.href = url;
        } else {
          setExportState(false, "Run a dataset audit before exporting.");
        }
      });
    }
  }

  function bindDemoLoaders() {
    async function loadDemoDataset(demoType, triggerLabel) {
      if (!demoType) {
        return;
      }

      const fileInput = document.getElementById("dataset-file-input");
      if (!fileInput) {
        return;
      }

      const response = await fetch(apiUrl(`/api/demo-dataset/${demoType}`));
      if (!response.ok) {
        throw new Error(`Failed to load demo: ${response.statusText}`);
      }

      const csvText = await response.text();
      const blob = new Blob([csvText], { type: "text/csv" });
      const file = new File([blob], `demo_${demoType}_dataset.csv`, { type: "text/csv" });
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      fileInput.files = dataTransfer.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));

      const fileNameDisplay = document.getElementById("file-name-display");
      if (fileNameDisplay) {
        const demoLabel = {
          credit: "Demo: Lending Bias (Age Proxy)",
          resume: "Demo: Hiring Bias (Gender Proxy)",
          policing: "Demo: Policing Bias (Race/Neighborhood Proxy)",
        }[demoType] || triggerLabel || `Demo: ${demoType}`;
        fileNameDisplay.textContent = demoLabel;
      }
    }

    const demoButtons = Array.from(document.querySelectorAll(".demo-loader-btn"));
    demoButtons.forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        const demoType = btn.dataset.demoType;
        if (!demoType) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "Loading demo...";

        try {
          await loadDemoDataset(demoType);
        } catch (error) {
          console.error("Demo load error:", error);
          alert(`Failed to load demo: ${error.message}`);
        } finally {
          btn.disabled = false;
          btn.textContent = originalText;
        }
      });
    });

    const params = new URLSearchParams(window.location.search);
    const requestedDemo = params.get("demo");
    if (requestedDemo) {
      loadDemoDataset(requestedDemo).catch((error) => {
        console.error("Auto demo load error:", error);
      });
    }
  }

  function bindExportButtons() {
    const colabBtn = document.getElementById("export-colab-btn");
    const whatIfBtn = document.getElementById("export-what-if-btn");
    setExportState(false);

    if (colabBtn) {
      colabBtn.addEventListener("click", () => {
        const url = buildExportUrl("colab");
        if (!url) {
          setExportState(false, "Run a dataset audit before exporting.");
          return;
        }
        window.location.href = url;
      });
    }

    if (whatIfBtn) {
      whatIfBtn.addEventListener("click", () => {
        const url = buildExportUrl("what-if");
        if (!url) {
          setExportState(false, "Run a dataset audit before exporting.");
          return;
        }
        window.location.href = url;
      });
    }
  }

  function generateReportWindow() {
    if (!currentAnalysisResult) return;
    
    const reportWindow = window.open("", "_blank");
    const aiMarkdownPayload = JSON.stringify(normalizeAiProseMarkdown(currentAiMarkdown || ""));
    const rankings = (currentAnalysisResult.stats && currentAnalysisResult.stats.group_rankings) || [];
    
    const html = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>Bias Analysis Report - bAIsed</title>
        <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
          :root {
            --teal: #0f766e;
            --teal-soft: #f0fdfa;
            --ink: #0f172a;
            --muted: #475569;
            --line: #dbe5e1;
            --page: #f8fafc;
          }
          @media print {
            .no-print { display: none; }
            body { background: #fff !important; padding: 0 !important; }
            .report-card { box-shadow: none !important; border: 0 !important; border-radius: 0 !important; max-width: 100% !important; }
            * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          }
          body {
            background: linear-gradient(160deg, #f8fafc, #eef6f3);
            padding: 32px;
            font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
            color: var(--ink);
          }
          .report-card {
            background: white;
            border-radius: 20px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 12px 40px rgba(2, 8, 23, 0.08);
            padding: 36px;
            max-width: 980px;
            margin: 0 auto;
          }
          .kpi {
            background: var(--teal-soft);
            border: 1px solid #ccfbf1;
            border-radius: 16px;
            padding: 16px;
          }
          .section-title {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            font-weight: 800;
            color: #0f766e;
            margin-bottom: 10px;
          }
          .ai-report {
            margin-top: 8px;
            border-top: 1px solid var(--line);
            padding-top: 20px;
          }
          .ai-report h1, .ai-report h2, .ai-report h3 {
            color: #0f172a;
            font-weight: 800;
            margin-top: 1.25rem;
            margin-bottom: 0.65rem;
            line-height: 1.25;
          }
          .ai-report h3 {
            font-size: 1.02rem;
            padding-left: 10px;
            border-left: 4px solid #14b8a6;
            background: #f8fffd;
          }
          .ai-report p, .ai-report li {
            color: #1e293b;
            line-height: 1.75;
            font-size: 0.97rem;
          }
          .ai-report ul { margin-top: 0.4rem; margin-bottom: 0.9rem; }
          .ai-report blockquote {
            border-left: 4px solid #14b8a6;
            background: #f0fdfa;
            border-radius: 0 10px 10px 0;
            padding: 10px 14px;
            margin: 12px 0;
          }
          .ai-report strong { color: #0f172a; }
        </style>
      </head>
      <body>
        <div class="no-print mb-8 text-center">
          <button onclick="window.print()" class="bg-slate-900 text-white px-6 py-2 rounded-lg font-semibold hover:bg-slate-800 transition">Print / Save as PDF</button>
        </div>
        
        <div class="report-card">
          <div class="flex justify-between items-start border-b pb-8 mb-8">
            <div>
              <h1 class="text-3xl font-black text-slate-900">bAIsed</h1>
              <p class="text-slate-500 uppercase tracking-widest text-xs font-bold mt-1">Bias Audit Report</p>
            </div>
            <div class="text-right">
              <p class="text-sm font-medium text-slate-600">Generated on ${new Date().toLocaleDateString()}</p>
              <p class="text-xs text-slate-400 mt-1">ID: BA-${Math.random().toString(36).substr(2, 9).toUpperCase()}</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-8 mb-12">
            <div class="bg-teal-50 p-6 rounded-2xl border border-teal-100">
              <p class="text-xs font-bold uppercase tracking-widest text-teal-600 mb-2">Most Advantaged Group</p>
              <p class="text-2xl font-black text-slate-900">${currentAnalysisResult.most_advantaged_group}</p>
            </div>
            <div class="bg-red-50 p-6 rounded-2xl border border-red-100">
              <p class="text-xs font-bold uppercase tracking-widest text-red-600 mb-2">Least Advantaged Group</p>
              <p class="text-2xl font-black text-slate-900">${currentAnalysisResult.least_advantaged_group}</p>
            </div>
          </div>

          <div class="mb-12">
            <h2 class="text-xl font-bold text-slate-900 mb-6">Group Selection Rate Comparison</h2>
            <div style="height: 300px;">
              <canvas id="reportChart"></canvas>
            </div>
          </div>

          <div class="prose prose-slate max-w-none prose-headings:text-slate-900 prose-strong:text-slate-900 prose-blockquote:border-l-4 prose-blockquote:border-teal-500 prose-blockquote:bg-teal-50 prose-blockquote:px-6 prose-blockquote:py-4 prose-blockquote:rounded-r-xl">
            <div class="section-title">AI Deep Analysis</div>
            <div id="report-ai-content" class="ai-report"></div>
          </div>

          <div class="mt-12 pt-8 border-t text-center text-xs text-slate-400 italic">
            This report was generated using bAIsed deterministic metrics and AI synthesis. 
            Final decisions should involve human oversight.
          </div>
        </div>

        <script>
          const rawAiMarkdown = ${aiMarkdownPayload};
          const aiContainer = document.getElementById("report-ai-content");
          if (aiContainer) {
            aiContainer.innerHTML = marked.parse(rawAiMarkdown || "_No AI analysis text available._");
          }

          const ctx = document.getElementById('reportChart').getContext('2d');
          new Chart(ctx, {
            type: 'bar',
            data: {
              labels: ${JSON.stringify(rankings.map(r => r.group))},
              datasets: [{
                label: 'Selection Rate',
                data: ${JSON.stringify(rankings.map(r => r.selection_rate))},
                backgroundColor: ${JSON.stringify(rankings.map(r => 
                  r.group === currentAnalysisResult.most_advantaged_group ? '#14b8a6' : 
                  r.group === currentAnalysisResult.least_advantaged_group ? '#ef4444' : '#64748b'
                ))},
                borderRadius: 8
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                y: { beginAtZero: true, max: 1, ticks: { format: { style: 'percent' } } }
              }
            }
          });
        </script>
      </body>
      </html>
    `;
    
    reportWindow.document.write(html);
    reportWindow.document.close();
  }

  function bindSimulator() {
    const slider = document.getElementById("simulator-diversity-weight");
    const valDisplay = document.getElementById("simulator-diversity-value");
    const constraintBtns = document.querySelectorAll("[data-simulator-constraint]");
    const constraintText = document.getElementById("simulator-constraint-text");

    if (slider) {
      slider.addEventListener("input", (e) => {
        if (valDisplay) valDisplay.textContent = e.target.value;
        requestSimulatorPreview();
      });
    }

    if (constraintBtns.length > 0) {
      constraintBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
          constraintBtns.forEach(b => {
            b.className = "rounded-xl border border-outline-variant px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-surface-container-low";
          });
          const clicked = e.target;
          clicked.className = "rounded-xl border border-secondary bg-secondary/10 px-4 py-2 text-sm font-semibold text-secondary transition";
          
          const constraint = clicked.getAttribute("data-simulator-constraint");
          if (constraintText) constraintText.textContent = constraint;
          requestSimulatorPreview();
        });
      });
    }
  }

  function bindGlobalReset() {
    const btn = document.getElementById("global-reset-btn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to clear all temporary datasets from the server? This will also reset your current analysis.")) {
        return;
      }

      try {
        btn.disabled = true;
        const originalContent = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">sync</span> Resetting...';

        const response = await fetch(apiUrl("/reset"), { method: "POST" });
        const result = await response.json();

        if (result.error) {
          alert("Reset failed: " + result.error);
        } else {
          // Clear localStorage as well
          localStorage.removeItem(LAST_RESULT_KEY);
          alert(result.message);
          window.location.reload();
        }
      } catch (error) {
        console.error("Reset error:", error);
        alert("Failed to reset server cache.");
      } finally {
        btn.disabled = false;
      }
    });
  }

  function bindDownloadReport() {
    const btn = document.getElementById("download-report-btn");
    if (btn) {
      btn.addEventListener("click", generateReportWindow);
    }
  }

  // ── Explainer Chat State ──────────────────────────────────────────────────────
  let explainerHistory = [];

  function showExplainerPanel() {
    const el = document.getElementById('explainer-panel');
    if (el) {
      el.classList.remove('hidden');
      el.style.display = 'block';
    }
  }

  function appendMessage(role, text) {
    const thread = document.getElementById('chat-thread');
    if (!thread) return null;
    const msg = document.createElement('div');
    if (role === 'user') {
      msg.className = "max-w-[85%] self-end rounded-xl bg-violet-600 p-3 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap";
    } else {
      msg.className = "max-w-[85%] self-start rounded-xl border border-slate-100 bg-white p-3 text-sm leading-relaxed text-slate-700 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 whitespace-pre-wrap";
    }
    msg.textContent = text;
    thread.appendChild(msg);
    thread.scrollTop = thread.scrollHeight;
    return msg;
  }


  async function sendExplainerMessage() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    if (privacyModeEnabled) {
      appendMessage('assistant', 'Privacy Mode is on, so AI chat is disabled. Generate a deterministic report instead.');
      return;
    }
    const userText = input.value.trim();
    if (!userText) return;
    if (!currentMetrics || !currentDatasetMeta) {
      appendMessage('assistant', 'Run a dataset or model audit first so I have metrics to explain.');
      return;
    }
    input.value = '';

    // Add user message to UI and history
    appendMessage('user', userText);
    explainerHistory.push({ role: 'user', content: userText });

    // Placeholder for streaming response
    const aiMsg = appendMessage('assistant', '');
    if (!aiMsg) return;
    let fullReply = '';

    try {
      const res = await fetch(apiUrl('/api/explain'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: explainerHistory,
          metrics: currentMetrics,
          dataset_meta: currentDatasetMeta,
        }),
      });

      if (!res.ok) {
        throw new Error(`Explain endpoint returned error ${res.status}`);
      }

      if (!res.body) {
        throw new Error("Explain endpoint did not return a readable stream.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let bufferedText = '';
      let streamFinished = false;

      while (true) {
        const { done, value } = await reader.read();
        bufferedText += decoder.decode(value || new Uint8Array(), { stream: !done });
        const events = bufferedText.split('\n\n');
        bufferedText = events.pop() || '';

        for (const eventText of events) {
          const payload = eventText
            .split('\n')
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trim())
            .join('\n')
            .trim();
          if (!payload) continue;
          if (payload === '[DONE]') {
            streamFinished = true;
            break;
          }
          try {
            const data = JSON.parse(payload);
            if (data.error) {
              fullReply = `Error: ${data.error}`;
              aiMsg.textContent = fullReply;
              aiMsg.className = "max-w-[85%] self-start rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-relaxed text-red-700 shadow-sm whitespace-pre-wrap";
              streamFinished = true;
              break;
            }
            if (data.chunk) {
              fullReply += data.chunk;
              aiMsg.textContent = fullReply;
            }
          } catch (e) {
            console.error("Error parsing stream chunk:", e);
          }
          const thread = document.getElementById('chat-thread');
          if (thread) thread.scrollTop = 9999;
        }
        if (done || streamFinished) break;
      }

      if (!fullReply) {
        fullReply = 'The explainer returned an empty response. Please check the Process 2 model configuration and try again.';
        aiMsg.textContent = fullReply;
        aiMsg.className = "max-w-[85%] self-start rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-relaxed text-amber-800 shadow-sm whitespace-pre-wrap";
      }

      // Commit completed reply to history if not an error
      if (!fullReply.startsWith('Error:')) {
        explainerHistory.push({ role: 'assistant', content: fullReply });
        queueSessionSave();
      }

    } catch (err) {
      aiMsg.textContent = `Error reaching the explainer: ${describeRequestError(err)}`;
      aiMsg.className = "max-w-[85%] self-start rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-relaxed text-red-700 shadow-sm whitespace-pre-wrap";
      console.error(err);
    }
  }

  window.sendExplainerMessage = sendExplainerMessage;
  window.showExplainerPanel = showExplainerPanel;

  document.addEventListener("DOMContentLoaded", () => {
    bindSimpleForm();
    bindScanOnSelect();
    bindDragAndDrop();
    bindAuditFlipControls();
    bindDatasetForm();
    bindModelAuditForm();
    bindAiAnalyzerForm();
    bindPrivacyModeToggle();
    bindSessionControls();
    bindSidebarToggle();
    bindDownloadReport();
    bindDemoLoaders();
    bindExportButtons();
    bindGlobalReset();
    bindSimulator();
    setupPuppyInteractions();
  });
})();
