(function () {
  const LAST_RESULT_KEY = "baised:last_fairness_result";
  let currentAnalysisResult = null;
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
    
    if (!overlay) return await taskFn();

    // Reset state
    puppyPetCount = 0;
    if (counter) counter.textContent = "0";
    overlay.classList.remove("hidden");
    overlay.classList.add("flex");
    
    let secondsLeft = 5;
    if (timer) timer.textContent = `${secondsLeft}s`;

    // Start task immediately in background
    const taskPromise = taskFn();
    
    // Force wait for at least 5 seconds
    await new Promise((resolve) => {
      const countdown = setInterval(() => {
        secondsLeft--;
        if (timer) timer.textContent = `${secondsLeft}s`;
        
        if (secondsLeft <= 0) {
          clearInterval(countdown);
          resolve();
        }
      }, 1000);
    });

    const result = await taskPromise;
    overlay.classList.add("hidden");
    overlay.classList.remove("flex");
    return result;
  }

  function persistLastResult(result) {
    try {
      localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(result || {}));
    } catch (error) {
      // Ignore storage failures (private mode / quota).
    }
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

  function renderResult(result) {
    currentAnalysisResult = result;
    const tone = severityTone(result.severity);
    setText("result-mode-chip", result.mode === "dataset" ? "Dataset" : "Simple");
    setText("severity-text", result.severity);
    setText("bias-detected-text", result.bias_detected ? "Bias detected below the 0.8 DIR threshold." : "No bias detected under the 0.8 DIR threshold.");
    setText("bias-score-text", formatDecimal(result.bias_score, 1));
    setText("dir-text", formatDecimal(result.DIR, 4));
    setText("difference-text", formatDecimal(result.difference, 4));
    setText("parity-text", formatPercent(result.stats.parity_percent));
    setText("eod-text", formatDecimal(result.metrics?.EOD || 0, 4));
    setText("aod-text", formatDecimal(result.metrics?.AOD || 0, 4));
    setText("explanation-text", result.explanation);
    setText("advantaged-group-text", result.most_advantaged_group);
    setText("disadvantaged-group-text", result.least_advantaged_group);
    setText("selection-gap-percent-text", formatPercent(result.stats.selection_gap_percent));
    setText("influential-feature-text", result.most_influential_feature || "-");
    setText("hidden-bias-text", result.hidden_bias_detected ? "Yes" : "No");

    const meta = [];
    if (result.mode === "dataset") {
      if (result.file_name) {
        meta.push(`File: ${result.file_name}`);
      }
      if (result.row_count !== undefined) {
        meta.push(`Rows: ${result.row_count}`);
      }
      if (result.protected_attribute) {
        meta.push(`Protected attribute: ${result.protected_attribute}`);
      }
      if (result.derived_protected && result.derived_protected.source_column) {
        meta.push(
          `Derived groups: ${result.derived_protected.source_column} via ${result.derived_protected.strategy}`,
        );
      }
      if (result.outcome_column) {
        meta.push(`Outcome column: ${result.outcome_column}`);
      }
      if (result.derived_outcome && result.derived_outcome.source_column) {
        meta.push(
          `Derived outcome: ${result.derived_outcome.source_column} >= ${result.derived_outcome.threshold}`,
        );
      }
    } else {
      meta.push("Simple input mode using groupA and groupB percentages.");
    }
    setText("dataset-meta-text", meta.join(" | "));

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
    renderGroupBars(result);
    renderHotspots(result);
    renderSimulations(result);
    renderRepairs(result);
    renderFeatureImpact(result);
    renderWarnings(result);
    persistLastResult(result);
    requestSimulatorPreview();
  }

  function renderError(message) {
    currentAnalysisResult = null;
    setText("result-mode-chip", "Error");
    setText("severity-text", "Unable To Analyze");
    setText("bias-detected-text", "The request did not complete.");
    setText("explanation-text", message);
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
    setText("hotspot-count-chip", "0 Hotspots");
    setText("simulation-count-chip", "0 Scenarios");
    setText("repair-count-chip", "0 Suggestions");
    setText("feature-count-chip", "0 Features");
    setText("warning-count-chip", "0 Warnings");
  }

  async function requestSimulatorPreview() {
    const slider = document.getElementById("simulator-diversity-weight");
    const constraintText = document.getElementById("simulator-constraint-text");
    if (!slider || !constraintText) {
      return;
    }

    try {
      const preview = await postJson("/simulate", {
        diversity_weight: Number(slider.value || 0.75),
        fairness_constraint: constraintText.textContent || "Optimal",
        analysis_result: currentAnalysisResult,
      });

      if (preview.error) {
        return;
      }

      setText("simulator-instant-label", preview.instant_label || "Instant");
      setText("simulator-change-text", preview.change || "-");
      setText("simulator-dir-text", formatDecimal(preview.metrics?.new_DIR || 0, 2));
      setText("simulator-spd-text", formatDecimal(preview.metrics?.new_SPD || 0, 2));
      setText("simulator-accuracy-text", formatPercent(preview.metrics?.estimated_accuracy || 0));
      setText("simulator-improvement-text", formatSignedPercent(preview.metrics?.parity_improvement_percent || 0));

      const improvementBar = document.getElementById("simulator-improvement-bar");
      if (improvementBar) {
        const width = Math.max(0, Math.min(100, Number(preview.metrics?.parity_improvement_percent || 0) * 10));
        improvementBar.style.width = `${width}%`;
      }
    } catch (error) {
      // Keep the simulator card stable if preview generation fails.
    }
  }

  function bindSimulator() {
    const slider = document.getElementById("simulator-diversity-weight");
    const value = document.getElementById("simulator-diversity-value");
    const constraintText = document.getElementById("simulator-constraint-text");
    const buttons = Array.from(document.querySelectorAll("[data-simulator-constraint]"));

    if (!slider || !value || !constraintText) {
      return;
    }

    const applyConstraintState = (selected) => {
      constraintText.textContent = selected;
      buttons.forEach((button) => {
        const active = button.dataset.simulatorConstraint === selected;
        button.className = active
          ? "rounded-xl border border-secondary bg-secondary/10 px-4 py-2 text-sm font-semibold text-secondary transition"
          : "rounded-xl border border-outline-variant px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-surface-container-low";
      });
    };

    slider.addEventListener("input", () => {
      value.textContent = Number(slider.value || 0).toFixed(2);
      requestSimulatorPreview();
    });

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const selected = button.dataset.simulatorConstraint || "Optimal";
        applyConstraintState(selected);
        requestSimulatorPreview();
      });
    });

    applyConstraintState("Optimal");
    value.textContent = Number(slider.value || 0).toFixed(2);
    requestSimulatorPreview();
  }

  async function postJson(url, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000); // 60 second timeout
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        const text = await response.text();
        console.error(`HTTP ${response.status}:`, text);
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
      return response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  async function postForm(url, formData) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000); // 60 second timeout
    try {
      const response = await fetch(url, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      if (!response.ok) {
        const text = await response.text();
        console.error(`HTTP ${response.status}:`, text);
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
      return response.json();
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
      formData.append("file", file);

      const protectedAttribute = document.getElementById("protected-attribute-input").value.trim();
      const outcomeColumn = document.getElementById("outcome-column-input").value.trim();
      const qualificationColumn = document.getElementById("qualification-column-input").value.trim();

      if (protectedAttribute) {
        formData.append("protected_attribute", protectedAttribute);
      }

      if (outcomeColumn) {
        formData.append("outcome_column", outcomeColumn);
      }

      if (qualificationColumn) {
        formData.append("qualification_column", qualificationColumn);
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
          : `Upload failed: ${error.message || error}`;
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
      
      resultPanel.classList.add("hidden");
      errorPanel.classList.add("hidden");

      if (!file || !currentAnalysisResult) {
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
      formData.append("file", file);
      formData.append("analysis_json", JSON.stringify(currentAnalysisResult));
      
      try {
        const result = await triggerPuppyDelay(() => postForm("/ai-analyze", formData));
        
        if (result.error) {
          document.getElementById("ai-error-text").textContent = result.error;
          errorPanel.classList.remove("hidden");
        } else {
          document.getElementById("ai-model-name").textContent = result.model || "Unknown Model";
          document.getElementById("ai-row-count").textContent = result.row_count || "0";
          document.getElementById("ai-response-text").innerHTML = marked.parse(result.ai_response || "");
          resultPanel.classList.remove("hidden");
        }
      } catch (error) {
        document.getElementById("ai-error-text").textContent = error.message || String(error);
        errorPanel.classList.remove("hidden");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Generate Detailed AI Report";
        if (spinner) {
          spinner.classList.add("hidden");
          spinner.classList.remove("animate-spin");
        }
      }
    });
  }

  function generateReportWindow() {
    if (!currentAnalysisResult) return;
    
    const reportWindow = window.open("", "_blank");
    const aiContent = document.getElementById("ai-response-text").innerHTML;
    const rankings = (currentAnalysisResult.stats && currentAnalysisResult.stats.group_rankings) || [];
    
    const html = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>Bias Analysis Report - bAIsed</title>
        <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
          @media print { .no-print { display: none; } }
          body { background: #f8fafc; padding: 40px; font-family: sans-serif; }
          .report-card { background: white; border-radius: 16px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); padding: 40px; max-width: 900px; margin: 0 auto; }
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
            ${aiContent}
          </div>

          <div class="mt-12 pt-8 border-t text-center text-xs text-slate-400 italic">
            This report was generated using bAIsed deterministic metrics and AI synthesis. 
            Final decisions should involve human oversight.
          </div>
        </div>

        <script>
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

  function bindDownloadReport() {
    const btn = document.getElementById("download-report-btn");
    if (btn) {
      btn.addEventListener("click", generateReportWindow);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindSimpleForm();
    bindDatasetForm();
    bindAiAnalyzerForm();
    bindDownloadReport();
    bindSimulator();
    setupPuppyInteractions();
  });
})();
