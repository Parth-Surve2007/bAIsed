(function () {
  const API_BASE = (window.BAISED_API_BASE || "").replace(/\/$/, "");
  const LAST_RESULT_KEY = "baised:last_fairness_result";
  let currentAnalysisResult = null;
  let currentDatasetId = null;
  let currentModelDatasetId = null;
  let currentAiMarkdown = "";
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

    try {
      return await taskPromise;
    } finally {
      overlay.classList.add("hidden");
      overlay.classList.remove("flex");
    }
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
    if (normalized === "HIGH") return "bg-red-100 text-red-700";
    if (normalized === "MEDIUM") return "bg-amber-100 text-amber-700";
    return "bg-emerald-100 text-emerald-700";
  }

  function renderProxyAnalysis(result) {
    const container = document.getElementById("proxy-analysis-list");
    const chip = document.getElementById("proxy-count-chip");
    if (!container || !chip) return;

    const proxies = result.proxy_analysis || [];
    chip.textContent = `${proxies.length} Found`;
    container.innerHTML = "";

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
          <span class="rounded-full px-2.5 py-1 text-xs font-semibold ${riskTone(item.risk)}">${item.risk}</span>
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
    chip.className = `rounded-full px-3 py-1 text-xs font-semibold ${hasRisk ? riskTone(risk.risk_level) : "bg-slate-100 text-slate-600"}`;
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
    chip.textContent = pattern.confidence !== undefined ? `${Math.round(pattern.confidence * 100)}%` : "--";
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
    currentAnalysisResult = result;
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

    const meta = [];
    if (result.mode === "dataset" || result.mode === "model") {
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
        meta.push(`${result.mode === "model" ? "Prediction column" : "Outcome column"}: ${result.outcome_column}`);
      }
      if (result.derived_outcome && result.derived_outcome.source_column) {
        meta.push(
          `Derived outcome: ${result.derived_outcome.source_column} >= ${result.derived_outcome.threshold}`,
        );
      }
      if (result.model_audit) {
        meta.push(`Model: ${result.model_audit.model_file_name}`);
        meta.push(`Loader: ${result.model_audit.model_type}`);
      }
      if (result.model_performance_by_group?.disparities) {
        const gaps = result.model_performance_by_group.disparities;
        if (gaps.error_rate_gap !== null && gaps.error_rate_gap !== undefined) {
          meta.push(`Error gap: ${formatDecimal(gaps.error_rate_gap, 4)}`);
        }
        if (gaps.true_positive_rate_gap !== null && gaps.true_positive_rate_gap !== undefined) {
          meta.push(`TPR gap: ${formatDecimal(gaps.true_positive_rate_gap, 4)}`);
        }
        if (gaps.false_positive_rate_gap !== null && gaps.false_positive_rate_gap !== undefined) {
          meta.push(`FPR gap: ${formatDecimal(gaps.false_positive_rate_gap, 4)}`);
        }
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

  async function postForm(url, formData) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000); // AI analysis may call Gemini
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

      const formData = new FormData();
      formData.append("file", file);

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
        
        if (!scanResult || scanResult.error) {
          console.error("Scan API error:", scanResult?.error);
          renderError(scanResult?.error || "Empty response from server");
          return;
        }
        
        if (!scanResult.columns || scanResult.columns.length === 0) {
           throw new Error("No columns detected in the file.");
        }

        if (scanResult.dataset_id) {
            currentDatasetId = scanResult.dataset_id;
        }
        
        // Populate dropdowns with intelligence
        populateDropdowns(scanResult.columns, scanResult.profile);
        console.log("Dropdowns populated with", scanResult.columns.length, "columns.");
        
        // Show field analysis immediately
        renderFieldAnalysis({ stats: { column_profile: scanResult.profile } });
        
        // Update UI state
        document.getElementById('file-drop-zone').classList.add('border-secondary','bg-secondary/10');
        document.getElementById('file-drop-zone').classList.remove('border-secondary/40','bg-secondary/5');
        document.getElementById('file-name-display').textContent = file.name;
        
        window.lastUploadedDatasetFile = file;

      } catch (err) {
        console.error("Scan error:", err);
        renderError(err.message || "Failed to scan dataset schema.");
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

    if (bestProtected.score > 2.0) {
      protectedSelect.value = bestProtected.name;
    }
    if (bestOutcome.score > 3.0) {
      trueLabelSelect.value = bestOutcome.name;
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

  function bindAuditFlipControls() {
    const showModelBtn = document.getElementById("show-model-audit");
    const showDatasetBtn = document.getElementById("show-dataset-audit");
    if (showModelBtn) {
      showModelBtn.addEventListener("click", () => setAuditFlipMode("model"));
    }
    if (showDatasetBtn) {
      showDatasetBtn.addEventListener("click", () => setAuditFlipMode("dataset"));
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
      window.lastUploadedDatasetFile = null;

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

    testInput.addEventListener("change", async () => {
      const file = testInput.files && testInput.files[0];
      const display = document.getElementById("model-test-file-name-display");
      currentModelDatasetId = null;
      if (!file) {
        if (display) display.textContent = "No test data selected";
        return;
      }
      if (display) display.textContent = `Scanning ${file.name}...`;

      const formData = new FormData();
      formData.append("file", file);
      try {
        const scanResult = await postForm("/scan", formData);
        if (scanResult.error) {
          renderError(scanResult.error);
          return;
        }
        currentModelDatasetId = scanResult.dataset_id || null;
        populateModelDropdowns(scanResult.columns || [], scanResult.profile || {});
        if (display) display.textContent = file.name;
      } catch (error) {
        console.error("Model test data scan error:", error);
        renderError(error.message || "Failed to scan model test data.");
        if (display) display.textContent = "Scan failed";
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const testFile = testInput.files && testInput.files[0];
      const modelFileInput = document.getElementById("model-file-input");
      const modelFile = modelFileInput?.files && modelFileInput.files[0];
      const protectedAttribute = document.getElementById("model-protected-attribute-input")?.value || "";
      const trueLabelColumn = document.getElementById("model-true-label-column-input")?.value || "";
      const qualificationColumn = document.getElementById("model-qualification-column-input")?.value || "";

      if (!testFile && !currentModelDatasetId) {
        renderError("Please choose a CSV or XLSX test dataset for the model audit.");
        return;
      }
      if (!modelFile) {
        renderError("Please choose a .pkl, .joblib, or TensorFlow/Keras model file.");
        return;
      }
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
        const result = await triggerPuppyDelay(() => postForm("/model-upload", formData));
        if (result.error) {
          renderError(result.error);
          return;
        }
        renderResult(result);
      } catch (error) {
        console.error("Model audit error:", error);
        const errorMsg = error.name === "AbortError"
          ? "Model audit timed out. Please try a smaller test dataset."
          : `Model audit failed: ${error.message || error}`;
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
      const display = document.getElementById("model-test-file-name-display");
      if (display) display.textContent = "No test data selected";
      const protectedSelect = document.getElementById("model-protected-attribute-input");
      const trueLabelSelect = document.getElementById("model-true-label-column-input");
      const qualSelect = document.getElementById("model-qualification-column-input");
      if (protectedSelect) protectedSelect.innerHTML = '<option value="">Scan test data first</option>';
      if (trueLabelSelect) trueLabelSelect.innerHTML = '<option value="">Scan test data first</option>';
      if (qualSelect) qualSelect.innerHTML = '<option value="">Optional</option>';
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

      if ((!file && !currentDatasetId) || !currentAnalysisResult) {
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
      } else {
        formData.append("file", file);
      }
      formData.append("analysis_json", JSON.stringify(compactAnalysisPayload(currentAnalysisResult)));
      
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
            document.getElementById("ai-model-name").textContent = result._source || "Gemini";
            document.getElementById("ai-row-count").textContent = result._row_count || "0";
          } else {
            currentAiMarkdown = result.ai_response || "";
            document.getElementById("ai-model-name").textContent = result.model || "Unknown Model";
            document.getElementById("ai-row-count").textContent = result.row_count || "0";
          }
          document.getElementById("ai-response-text").innerHTML = marked.parse(currentAiMarkdown);
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
    const aiMarkdownPayload = JSON.stringify(currentAiMarkdown || "");
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

  document.addEventListener("DOMContentLoaded", () => {
    bindSimpleForm();
    bindScanOnSelect();
    bindDragAndDrop();
    bindAuditFlipControls();
    bindDatasetForm();
    bindModelAuditForm();
    bindAiAnalyzerForm();
    bindDownloadReport();
    bindDemoLoaders();
    bindExportButtons();
    bindGlobalReset();
    bindSimulator();
    setupPuppyInteractions();
  });
})();
