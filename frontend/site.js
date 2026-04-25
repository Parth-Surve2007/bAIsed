(() => {
  const routes = {
    home: "/app",
    solutions: "/app/solutions",
    methodology: "/app/methodology",
    caseStudies: "/app/case_study",
    pricing: "/app/pricing_demo",
    docs: "/app/documentation",
    login: "/app/login",
    workbench: "/app/workbench",
  };

  const routeMap = new Map([
    ["baised", routes.home],
    ["biasanalytica", routes.home],
    ["product", routes.solutions],
    ["solutions", routes.solutions],
    ["methodology", routes.methodology],
    ["case studies", routes.caseStudies],
    ["pricing", routes.pricing],
    ["docs", routes.docs],
    ["documentation", routes.docs],
    ["dashboard", routes.workbench],
    ["support", routes.docs],
    ["enterprise", routes.pricing],
    ["login", routes.login],
    ["sign in", routes.login],
    ["sign up", routes.login],
    ["get started", routes.workbench],
    ["request demo", routes.pricing],
    ["book demo", routes.pricing],
    ["start free audit", routes.workbench],
    ["start analyzing your data now", routes.workbench],
    ["explore hiring analytics", routes.caseStudies],
    ["read case study", routes.caseStudies],
    ["view full analysis", routes.caseStudies],
    ["schedule a consultation", routes.pricing],
    ["download whitepaper", "/api/downloads/whitepaper"],
    ["request custom demo", routes.pricing],
    ["explore documentation", routes.docs],
    ["schedule a solution briefing", routes.pricing],
    ["view all integration", routes.docs],
    ["start individual plan", routes.login],
    ["start 14 day free trial", routes.login],
    ["start 14-day free trial", routes.login],
    ["contact sales", routes.pricing],
    ["contact enterprise sales", routes.pricing],
    ["forgot password", routes.login],
    ["privacy policy", routes.docs],
    ["terms of service", routes.docs],
    ["security", routes.docs],
    ["contact", routes.docs],
    ["contact us", routes.docs],
    ["help", routes.docs],
    ["settings", routes.docs],
    ["status", routes.docs],
    ["quickstart guide", routes.docs + "#quick-start"],
    ["introduction", routes.docs + "#introduction"],
    ["architecture overview", routes.docs + "#metrics-engine"],
    ["authentication", routes.docs + "#api-reference"],
    ["endpoints", routes.docs + "#api-reference"],
    ["rate limits", routes.docs + "#api-reference"],
    ["bias detection", routes.docs + "#metrics-engine"],
    ["drift analytics", routes.docs + "#metrics-engine"],
    ["fairness ratios", routes.docs + "#metrics-engine"],
    ["next up quickstart guide", routes.docs + "#quick-start"],
    ["deploy audit", routes.workbench],
  ]);

  function normalizeText(value) {
    return (value || "")
      .replace(/[^\w\s-]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function getCurrentPage() {
    return document.body.dataset.page || "";
  }

  function getSessionUser() {
    const email = localStorage.getItem("baised_user_email");
    const token = localStorage.getItem("baised_demo_token");
    if (!email && !token) {
      return null;
    }

    const safeEmail = email || "signed-in user";
    const name = safeEmail.split("@")[0] || safeEmail;
    const initials = name
      .split(/[.\-_ ]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("") || "U";

    return { email: safeEmail, initials };
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element && value !== undefined && value !== null) {
      element.textContent = String(value);
    }
  }

  function setWidth(id, percent) {
    const element = document.getElementById(id);
    if (element && Number.isFinite(percent)) {
      element.style.width = `${percent}%`;
    }
  }

  function parseNumeric(value) {
    if (typeof value === "number") {
      return value;
    }
    const parsed = Number(String(value || "").replace(/[^\d.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  }

  const LAST_RESULT_KEY = "baised:last_fairness_result";

  function getStoredFairnessResult() {
    try {
      const raw = localStorage.getItem(LAST_RESULT_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (error) {
      return null;
    }
  }

  function formatPercent(value, digits = 1) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${numeric.toFixed(digits)}%`;
  }

  function formatDecimal(value, digits = 4) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return numeric.toFixed(digits);
  }

  function titleCase(value) {
    return String(value || "")
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .map((word) => word[0].toUpperCase() + word.slice(1))
      .join(" ");
  }

  function renderLandingGroupChart(result) {
    const container = document.getElementById("hero-group-chart");
    const countChip = document.getElementById("hero-group-count");
    if (!container || !countChip) {
      return;
    }

    const rankings = (result && result.stats && result.stats.group_rankings) || [];
    countChip.textContent = `${rankings.length} groups`;
    container.innerHTML = "";

    if (!rankings.length) {
      container.innerHTML =
        '<div class="rounded-2xl border border-dashed border-white/60 bg-white/30 px-5 py-6 text-sm text-on-surface-variant">No dataset stats yet. Upload a CSV/XLSX in the Workbench to populate this chart.</div>';
      return;
    }

    rankings.slice(0, 10).forEach((entry, index) => {
      const selectionRate = Number(entry.selection_rate);
      const percent = Number.isFinite(selectionRate) ? selectionRate * 100 : 0;
      const bar = document.createElement("div");
      bar.className = "rounded-2xl border border-white/60 bg-white/40 p-4 shadow-sm backdrop-blur-sm";

      const header = document.createElement("div");
      header.className = "mb-3 flex items-center justify-between gap-4";
      header.innerHTML = `
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-on-surface">${entry.group ?? `Group ${index + 1}`}</p>
          <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-on-surface-variant">Rank ${index + 1}</p>
        </div>
        <p class="shrink-0 text-sm font-black text-on-surface">${formatPercent(percent, 1)}</p>
      `;

      const meter = document.createElement("div");
      meter.className = "h-3 rounded-full bg-black/5 overflow-hidden";

      const fill = document.createElement("div");
      fill.className = "h-3 rounded-full";
      fill.style.width = `${Math.max(4, Math.min(100, percent))}%`;
      fill.style.backgroundColor = "#3a6662";

      meter.appendChild(fill);
      bar.appendChild(header);
      bar.appendChild(meter);
      container.appendChild(bar);
    });
  }

  function bindHeroCardTilt(result) {
    const card = document.getElementById("hero-score-card");
    if (!card) {
      return;
    }
    if (card.dataset.heroTiltBound === "true") {
      return;
    }
    card.dataset.heroTiltBound = "true";

    card.addEventListener("mousemove", (event) => {
      const bounds = card.getBoundingClientRect();
      const rotateX = ((event.clientY - bounds.top) / bounds.height - 0.5) * -8;
      const rotateY = ((event.clientX - bounds.left) / bounds.width - 0.5) * 10;
      card.style.transform = `perspective(1200px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
      card.style.boxShadow = "0 28px 60px rgba(15, 23, 42, 0.14)";
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform = "";
      card.style.boxShadow = "";
    });

    card.addEventListener("mouseenter", () => {
      const copy = document.getElementById("hero-parity-copy");
      if (!copy) {
        return;
      }
      if (result && result.most_advantaged_group && result.least_advantaged_group) {
        copy.textContent = `Largest gap: ${result.least_advantaged_group} vs ${result.most_advantaged_group}.`;
      }
    });

    card.addEventListener("mouseleave", () => {
      const copy = document.getElementById("hero-parity-copy");
      if (copy && copy.dataset.defaultText) {
        copy.textContent = copy.dataset.defaultText;
      }
    });
  }

  function getToastRoot() {
    let root = document.getElementById("site-toast-root");
    if (root) {
      return root;
    }

    root = document.createElement("div");
    root.id = "site-toast-root";
    root.className = "fixed bottom-4 left-1/2 z-[100] flex -translate-x-1/2 flex-col gap-2";
    document.body.appendChild(root);
    return root;
  }

  function showToast(message, tone = "info") {
    const root = getToastRoot();
    const toast = document.createElement("div");
    const toneClass =
      tone === "error"
        ? "border-red-200 bg-red-50 text-red-700"
        : "border-slate-200 bg-white text-slate-800";

    toast.className = `rounded-xl border px-4 py-3 text-sm shadow-lg ${toneClass}`;
    toast.textContent = message;
    root.appendChild(toast);

    window.setTimeout(() => {
      toast.remove();
    }, 3200);
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }
    return data;
  }

  function resolveRoute(element) {
    const explicitLabel = element.getAttribute("data-nav-label");
    const text = explicitLabel || element.textContent || "";
    return routeMap.get(normalizeText(text)) || null;
  }

  function attachRoute(element, href) {
    if (element.tagName === "A") {
      element.setAttribute("href", href);
      return;
    }

    element.style.cursor = "pointer";
    element.addEventListener("click", () => {
      window.location.href = href;
    });
  }

  function bindElements() {
    document.querySelectorAll("a[href='#'], button:not([data-action]), [data-nav-label]").forEach((element) => {
      if (element.dataset.routeBound === "true") {
        return;
      }

      if (element.tagName === "BUTTON" && element.getAttribute("type") === "submit") {
        return;
      }

      const route = resolveRoute(element);
      if (!route) {
        return;
      }

      attachRoute(element, route);
      element.dataset.routeBound = "true";
    });
  }

  function normalizeBranding() {
    const replacements = [
      ["BiasAnalytica AI", "bAIsed"],
      ["BiasAnalytica", "bAIsed"],
      ["Â© 2024", "© 2024"],
      ["© 2024 bAIsed AI.", "© 2024 bAIsed."],
    ];

    document.querySelectorAll("title, h1, h2, h3, h4, h5, h6, p, span, div, a, button").forEach((element) => {
      if (element.children.length > 0) {
        return;
      }

      let nextValue = element.textContent || "";
      replacements.forEach(([from, to]) => {
        nextValue = nextValue.replaceAll(from, to);
      });

      if (nextValue !== (element.textContent || "")) {
        element.textContent = nextValue;
      }
    });
  }

  function enhanceDocumentationAnchors() {
    const title = Array.from(document.querySelectorAll("h1")).find((el) =>
      /Introduction to bAIsed/i.test(el.textContent || "")
    );
    if (!title) {
      return;
    }

    title.id = "introduction";
    title.style.scrollMarginTop = "100px";

    const quickStart = Array.from(document.querySelectorAll("h2")).find((el) =>
      (el.textContent || "").trim() === "Quick Start"
    );
    if (quickStart) {
      quickStart.id = "quick-start";
      quickStart.style.scrollMarginTop = "100px";
    }

    const metricsEngine = Array.from(document.querySelectorAll("h2")).find((el) =>
      (el.textContent || "").trim() === "Metrics Engine Section"
    );
    if (metricsEngine) {
      metricsEngine.id = "metrics-engine";
      metricsEngine.style.scrollMarginTop = "100px";
    }

    const apiReferenceAnchor = document.querySelector("[data-api-reference-anchor]");
    if (apiReferenceAnchor) {
      apiReferenceAnchor.id = "api-reference";
      apiReferenceAnchor.style.scrollMarginTop = "100px";
    }
  }

  async function resolveAction(action) {
    return requestJson("/api/actions/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, page: getCurrentPage() }),
    });
  }

  function bindActionButtons() {
    document.querySelectorAll("[data-action]").forEach((element) => {
      if (element.dataset.actionBound === "true") {
        return;
      }

      element.dataset.actionBound = "true";
      element.style.cursor = "pointer";
      element.addEventListener("click", async (event) => {
        if (element.tagName === "A") {
          event.preventDefault();
        }

        const action = element.getAttribute("data-action") || element.textContent || "";
        try {
          const result = await resolveAction(action);
          showToast(result.message || "Action completed.");

          if (getCurrentPage() === "pricing_demo" && normalizeText(action).includes("demo")) {
            const demoForm = document.getElementById("demo-request-form");
            if (demoForm) {
              demoForm.scrollIntoView({ behavior: "smooth", block: "center" });
              return;
            }
          }

          if (result.target) {
            window.setTimeout(() => {
              window.location.href = result.target;
            }, 200);
          }
        } catch (error) {
          showToast(error.message, "error");
        }
      });
    });
  }

  function renderDocumentationResults(results) {
    const container = document.getElementById("docs-search-results");
    if (!container) {
      return;
    }

    container.innerHTML = "";
    if (!results.length) {
      container.innerHTML =
        '<div class="rounded-xl border border-dashed border-outline-variant bg-surface-container-low px-4 py-4 text-sm text-zinc-500">No matching documentation topics found.</div>';
      return;
    }

    results.forEach((item) => {
      const card = document.createElement("a");
      card.href = item.href;
      card.className =
        "block rounded-xl border border-outline-variant bg-surface-container-low px-4 py-4 transition hover:border-slate-400 hover:bg-white";
      card.innerHTML = `
        <p class="text-sm font-semibold text-zinc-900">${item.title}</p>
        <p class="mt-1 text-sm text-zinc-500">${item.summary}</p>
      `;
      container.appendChild(card);
    });
  }

  async function bindDocsSearch() {
    const input = document.getElementById("docs-search-input");
    if (!input) {
      return;
    }

    const search = async () => {
      try {
        const data = await requestJson(`/api/search?query=${encodeURIComponent(input.value)}`);
        renderDocumentationResults(data.results || []);
      } catch (error) {
        showToast(error.message, "error");
      }
    };

    input.addEventListener("input", () => {
      window.clearTimeout(input._searchTimer);
      input._searchTimer = window.setTimeout(search, 180);
    });

    await search();
  }

  function bindLoginFlow() {
    const form = document.getElementById("login-form");
    if (!form) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const email = document.getElementById("email");
      const password = document.getElementById("password");
      const remember = document.getElementById("remember");

      try {
        const result = await requestJson("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: email ? email.value : "",
            password: password ? password.value : "",
            remember: Boolean(remember && remember.checked),
          }),
        });

        localStorage.setItem("baised_demo_token", result.token);
        localStorage.setItem("baised_user_email", result.email);
        setText("login-status", `${result.message} Redirecting to the workbench...`);
        showToast(result.message);
        window.setTimeout(() => {
          window.location.href = result.redirect || routes.workbench;
        }, 250);
      } catch (error) {
        setText("login-status", error.message);
        showToast(error.message, "error");
      }
    });
  }

  function renderAuthState() {
    const user = getSessionUser();
    if (!user) {
      return;
    }

    document.querySelectorAll("[data-auth-container]").forEach((container) => {
      if (!container.querySelector("[data-user-pill]")) {
        const pill = document.createElement("a");
        pill.href = routes.workbench;
        pill.dataset.userPill = "true";
        pill.className =
          "hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 md:inline-flex md:items-center md:gap-2";
        pill.innerHTML = `<span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">${user.initials}</span><span>${user.email}</span>`;
        container.prepend(pill);
      }
    });

    document.querySelectorAll("[data-auth-container]").forEach((container) => {
      container.querySelectorAll("button, a").forEach((element) => {
        const action = element.getAttribute("data-action");
        const normalized = normalizeText(action || element.textContent || "");
        if (normalized !== "sign in" && normalized !== "login") {
          return;
        }

        element.textContent = user.email;
        element.setAttribute("data-action", "Dashboard");
        element.dataset.navLabel = "Dashboard";
      });
    });
  }

  function bindDemoRequestForm() {
    const form = document.getElementById("demo-request-form");
    if (!form) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      try {
        const result = await requestJson("/api/demo-request", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: document.getElementById("demo-name")?.value || "",
            email: document.getElementById("demo-email")?.value || "",
            company: document.getElementById("demo-company")?.value || "",
            use_case: document.getElementById("demo-use-case")?.value || "",
          }),
        });

        setText("demo-request-status", `${result.message} Request #${result.request_id}.`);
        showToast(result.message);
      } catch (error) {
        setText("demo-request-status", error.message);
        showToast(error.message, "error");
      }
    });
  }

  function renderLandingPage(data) {
    const hero = data.hero || {};
    const stored = getStoredFairnessResult();
    const result = stored && stored.stats && stored.stats.group_rankings ? stored : null;

    const parityPercent = result && result.stats ? Number(result.stats.parity_percent) : parseNumeric(hero.current_score);
    setText("hero-current-score", formatPercent(parityPercent, 1));

    const verdict =
      result && result.bias_detected !== undefined
        ? result.bias_detected
          ? `${titleCase(result.severity)} Bias Detected`
          : "No Bias Detected"
        : hero.status;
    setText("hero-status", verdict);

    setText("hero-dir", result ? formatDecimal(result.DIR, 4) : "-");
    setText("hero-selection-gap", result ? formatPercent(Number(result.stats?.selection_gap_percent), 1) : "-");

    const meta = [];
    if (result && result.file_name) {
      meta.push(`File: ${result.file_name}`);
    }
    if (result && result.row_count !== undefined) {
      meta.push(`Rows: ${result.row_count}`);
    }
    if (result && result.protected_attribute) {
      meta.push(`Protected: ${result.protected_attribute}`);
    }
    if (result && result.outcome_column) {
      meta.push(`Outcome: ${result.outcome_column}`);
    }
    setText(
      "hero-dataset-meta",
      meta.length ? meta.join(" | ") : "Upload a CSV/XLSX in the Workbench to see group stats here.",
    );

    const copy = document.getElementById("hero-parity-copy");
    const defaultCopy = result
      ? "Hover the card for the largest parity gap summary."
      : "Upload a dataset to replace the demo values with real group-level parity stats.";
    if (copy) {
      copy.textContent = defaultCopy;
      copy.dataset.defaultText = defaultCopy;
    }

    renderLandingGroupChart(result);
    bindHeroCardTilt(result);
    bindLandingSimulator();
  }

  function bindLandingSimulator() {
    const slider = document.getElementById("sim-diversity-slider");
    const value = document.getElementById("sim-diversity-value");
    const fill = document.getElementById("sim-gauge-fill");
    const riskLabel = document.getElementById("sim-risk-label");
    const accuracy = document.getElementById("sim-accuracy");
    const constraintLabel = document.getElementById("sim-constraint-label");
    const constraintButtons = Array.from(document.querySelectorAll("[data-sim-constraint]"));

    if (!slider || !value || !fill || !riskLabel || !accuracy) {
      return;
    }

    const circumference = Number(fill.getAttribute("stroke-dasharray")) || 283;

    const applyConstraint = (selected) => {
      if (constraintLabel) {
        constraintLabel.textContent = selected;
      }
      constraintButtons.forEach((button) => {
        const isActive = button.dataset.simConstraint === selected;
        button.className = isActive
          ? "py-2 px-4 rounded border border-secondary bg-secondary/10 text-secondary text-sm"
          : "py-2 px-4 rounded border border-zinc-700 text-sm hover:bg-zinc-800";
      });
      slider.dataset.simConstraint = selected;
      update();
    };

    const toneForRisk = (risk) => {
      if (risk <= 0.33) {
        return { label: "Low", color: "#13eed3" };
      }
      if (risk <= 0.66) {
        return { label: "Moderate", color: "#f59e0b" };
      }
      return { label: "High", color: "#ef4444" };
    };

    const update = () => {
      const raw = Number(slider.value);
      const normalized = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) / 100 : 0.65;
      value.textContent = normalized.toFixed(2);

      const constraint = slider.dataset.simConstraint || "Optimal";
      const constraintPenalty = constraint === "Loose" ? 0.08 : constraint === "Strict" ? -0.1 : 0;

      const risk = Math.max(0, Math.min(1, 1 - normalized));
      const tone = toneForRisk(risk);
      riskLabel.textContent = tone.label;
      fill.setAttribute("stroke", tone.color);

      const progress = Math.max(0, Math.min(1, normalized + constraintPenalty));
      const dashOffset = circumference * (1 - progress);
      fill.setAttribute("stroke-dashoffset", String(Math.max(0, Math.min(circumference, dashOffset))));

      const estimatedAccuracy = 96 - normalized * 6 - (constraint === "Strict" ? 1.2 : constraint === "Loose" ? -0.6 : 0);
      accuracy.textContent = `${Math.max(85, Math.min(99.9, estimatedAccuracy)).toFixed(1)}%`;
    };

    slider.addEventListener("input", update);
    slider.addEventListener("change", update);

    constraintButtons.forEach((button) => {
      button.addEventListener("click", () => applyConstraint(button.dataset.simConstraint || "Optimal"));
    });

    applyConstraint("Optimal");
    update();
  }

  function renderSolutionsPage(data) {
    const hiring = data.hiring || {};
    const finance = data.finance || {};
    const healthcare = data.healthcare || {};
    setText("solutions-hiring-ratio", hiring.pass_rate_ratio);
    setText("solutions-gender-parity", hiring.gender_parity);
    setText("solutions-compliance-rate", finance.compliance_rate);
    setText("solutions-adverse-impact", healthcare.adverse_impact);
    setText("solutions-data-density", healthcare.data_density);
  }

  function renderMethodologyPage(data) {
    setText("methodology-dir-equation", data.dir_equation);
    setText("methodology-threshold-title", data.threshold_title);
    setText("methodology-threshold-copy", data.threshold_copy);
    setText("methodology-statistical-parity-a", data.statistical_parity?.group_a);
    setText("methodology-statistical-parity-b", data.statistical_parity?.group_b);
    setText("methodology-equalized-odds-tpr", data.equalized_odds?.true_positive_rate);
    setText("methodology-equalized-odds-fpr", data.equalized_odds?.false_positive_rate);
    setText("methodology-baseline-dir", `DIR ${data.remediation?.baseline_dir}`);
    setText("methodology-remediated-dir", `DIR ${data.remediation?.optimized_dir}`);
    setWidth("methodology-baseline-bar", Number(data.remediation?.baseline_dir) * 100);
    setWidth("methodology-remediated-bar", Number(data.remediation?.optimized_dir) * 100);
  }

  function renderCaseStudyPage(data) {
    const featured = data.featured || {};
    const secondary = data.secondary || {};
    setText("case-feature-title", featured.title);
    setText("case-feature-summary", featured.summary);
    setText("case-feature-bias-reduction", featured.bias_reduction);
    setText("case-feature-hiring-speed", featured.hiring_speed);
    setText("case-credit-gap", secondary.credit_gap);
    setText("case-healthcare-parity", secondary.healthcare_parity);
    setText("case-public-sector-audit", secondary.public_sector_audit);
    setText("case-retail-bias", secondary.retail_bias);
  }

  function renderPricingPage(data) {
    const plans = data.plans || {};
    const cta = data.cta || {};
    setText("pricing-researcher-price", plans.researcher);
    setText("pricing-pro-team-price", plans.pro_team);
    setText("pricing-enterprise-price", plans.enterprise);
    setText("pricing-cta-headline", cta.headline);
    setText("pricing-cta-body", cta.body);
  }

  function renderDocumentationPage(data) {
    setText("docs-version", data.version);
    renderDocumentationResults(data.search_topics || []);
  }

  async function hydratePage() {
    const page = getCurrentPage();
    if (!page || page === "login" || page === "workbench") {
      return;
    }

    try {
      const data = await requestJson(`/api/site-content/${page}`);
      if (page === "landing") {
        renderLandingPage(data);
      } else if (page === "solutions") {
        renderSolutionsPage(data);
      } else if (page === "methodology") {
        renderMethodologyPage(data);
      } else if (page === "case_study") {
        renderCaseStudyPage(data);
      } else if (page === "pricing_demo") {
        renderPricingPage(data);
      } else if (page === "documentation") {
        renderDocumentationPage(data);
      }
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    normalizeBranding();
    renderAuthState();
    bindElements();
    bindActionButtons();
    enhanceDocumentationAnchors();
    bindLoginFlow();
    bindDemoRequestForm();
    await hydratePage();
    await bindDocsSearch();
    
    // Fun interactive pricing page logic
    if (getCurrentPage() === "pricing_demo") {
      const escapingBtn = document.getElementById("escaping-button");
      if (escapingBtn) {
        escapingBtn.addEventListener("mouseover", () => {
          const x = Math.random() * (window.innerWidth - escapingBtn.offsetWidth);
          const y = Math.random() * (window.innerHeight - escapingBtn.offsetHeight);
          escapingBtn.style.position = "fixed";
          escapingBtn.style.zIndex = "9999";
          escapingBtn.style.left = `${x}px`;
          escapingBtn.style.top = `${y}px`;
          escapingBtn.style.width = "200px";
        });
      }

      const smileBtn = document.getElementById("smile-button");
      if (smileBtn) {
        smileBtn.addEventListener("click", () => {
          const confettiCount = 100;
          const colors = ["#13eed3", "#000000", "#3a6662", "#f59e0b"];
          
          for (let i = 0; i < confettiCount; i++) {
            const confetti = document.createElement("div");
            confetti.style.position = "fixed";
            confetti.style.zIndex = "10000";
            confetti.style.width = "10px";
            confetti.style.height = "10px";
            confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            confetti.style.left = `${Math.random() * 100}vw`;
            confetti.style.top = "-10px";
            confetti.style.borderRadius = "2px";
            confetti.style.pointerEvents = "none";
            document.body.appendChild(confetti);

            const animation = confetti.animate([
              { transform: "translateY(0) rotate(0deg)", opacity: 1 },
              { transform: `translateY(100vh) rotate(${Math.random() * 360}deg)`, opacity: 0 }
            ], {
              duration: 2000 + Math.random() * 3000,
              easing: "cubic-bezier(0, .9, .57, 1)"
            });

            animation.onfinish = () => confetti.remove();
          }
          showToast("Thanks for the smile! You're awesome. 😊");
        });
      }
    }
  });
})();
