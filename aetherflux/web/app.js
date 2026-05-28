const state = {
  candidates: [],
  selected: [],
  foreign: [],
  opportunities: [],
  risks: [],
  draft: null,
  status: null,
};

const endpoints = {
  candidates: "/api/candidates",
  selected: "/api/selected",
  foreign: "/api/foreign-signals",
  opportunities: "/api/opportunities",
  risks: "/api/risks",
  draft: "/api/review-drafts/latest",
  status: "/api/system-status",
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("runIngest").addEventListener("click", runIngest);
  document.getElementById("runReview").addEventListener("click", runReview);
  refreshAll();
});

async function refreshAll() {
  const [candidates, selected, foreign, opportunities, risks, draft, status] = await Promise.all([
    getJson(endpoints.candidates),
    getJson(endpoints.selected),
    getJson(endpoints.foreign),
    getJson(endpoints.opportunities),
    getJson(endpoints.risks),
    getJson(endpoints.draft),
    getJson(endpoints.status),
  ]);
  state.candidates = candidates.items || [];
  state.selected = selected.items || [];
  state.foreign = foreign.items || [];
  state.opportunities = opportunities.items || [];
  state.risks = risks.items || [];
  state.draft = draft || {};
  state.status = status || {};
  render();
}

async function runIngest() {
  await postJson("/api/run-ingest", {});
  showToast("采集与基础评分已执行");
  await refreshAll();
}

async function runReview() {
  const draft = await postJson("/api/run-review", {});
  state.draft = draft;
  showToast("待审稿已生成");
  await refreshAll();
}

async function decide(id, status) {
  const input = document.querySelector(`[data-weight-for="${id}"]`);
  const weight = input ? input.value : "";
  await postJson("/api/decisions", {
    id,
    status,
    weight_override: weight,
    note: status === "approved" ? "人工确认进入输出" : "人工驳回",
  });
  showToast(status === "approved" ? "已确认进入网页/API" : "已驳回");
  await refreshAll();
}

function render() {
  setText("metricCandidates", state.candidates.length);
  setText("metricSelected", state.selected.length);
  setText("metricForeign", state.foreign.length);
  setText("metricRisks", state.risks.length);
  renderReadiness();
  renderDraft();
  renderList("selectedList", state.selected, false);
  renderList("foreignList", state.foreign, true);
  renderList("opportunityList", state.opportunities, true);
  renderList("riskList", state.risks, false);
}

function renderReadiness() {
  const target = document.getElementById("readinessGrid");
  const advisorStatus = document.getElementById("advisorStatus");
  const status = state.status || {};
  const modules = status.modules || {};
  const deepseek = status.deepseek || {};
  const connection = deepseek.connection || {};
  const firstPlatform = status.first_platform || {};
  const indicator = ["red", "yellow", "green"].includes(connection.indicator) ? connection.indicator : "red";
  advisorStatus.className = `pill advisor-pill status-${indicator}`;
  advisorStatus.title = connection.message || connection.label || "";
  advisorStatus.innerHTML = `
    <span class="status-dot" aria-hidden="true"></span>
    <span>${escapeHtml(`智库层 · ${deepseek.model || "未配置模型"}`)}</span>
  `;
  const cards = [
    {
      title: "小红书首采",
      meta: firstPlatform.status || "config_ready",
      body: firstPlatform.next_step || "准备接入正式采集适配器。",
    },
    {
      title: "交叉验证中心",
      meta: modules.cross_verification?.status || "ready_for_expansion",
      body: modules.cross_verification?.description || "claim、支持来源、冲突来源、补证建议。",
    },
    {
      title: "GEO 疑似度",
      meta: modules.geo_risk?.status || "ready_for_expansion",
      body: modules.geo_risk?.description || "信息污染与标准答案塑造风险概率。",
    },
    {
      title: "中英对照呈现",
      meta: modules.bilingual_display?.status || "ready",
      body: modules.bilingual_display?.description || "人工审阅和最终呈现阶段中英对照。",
    },
  ];
  target.innerHTML = cards.map((card) => `
    <article class="readiness-card">
      <span>${escapeHtml(card.meta)}</span>
      <h3>${escapeHtml(card.title)}</h3>
      <p>${escapeHtml(card.body)}</p>
    </article>
  `).join("");
}

function renderDraft() {
  const panel = document.getElementById("reviewDraft");
  const status = document.getElementById("reviewStatus");
  const draft = state.draft;
  if (!draft || !draft.id) {
    panel.className = "review-panel empty-state";
    panel.textContent = "暂无待审稿。运行采集后生成审议草稿。";
    status.textContent = "等待生成";
    return;
  }
  status.textContent = "待人工确认";
  panel.className = "review-panel";
  const roles = Object.values(draft.role_assessments || {});
  const selected = draft.selected || [];
  panel.innerHTML = `
    <p class="draft-summary">${escapeHtml(draft.summary || "")}</p>
    <div class="role-grid">
      ${roles.map((role) => `
        <article class="role-tile">
          <strong>${escapeHtml(role.label || "")}</strong>
          <p>${escapeHtml(role.view || "")}</p>
        </article>
      `).join("")}
    </div>
    <div class="item-list">
      ${selected.map((item) => cardHtml(item, false, true)).join("") || `<div class="empty-state">没有达到阈值的待审条目。</div>`}
    </div>
  `;
  bindDecisionButtons(panel);
}

function renderList(targetId, items, compact) {
  const target = document.getElementById(targetId);
  if (!items.length) {
    target.innerHTML = `<div class="empty-state">暂无已确认数据。</div>`;
    return;
  }
  target.innerHTML = items.map((item) => cardHtml(item, compact, false)).join("");
}

function cardHtml(item, compact, actionable) {
  const signals = item.signals || [];
  const display = item.display || {};
  const titleZh = display.title_zh || (item.language === "zh" ? item.title : "");
  const titleEn = display.title_en || (item.language === "en" ? item.title : "");
  const summaryZh = display.summary_zh || (item.language === "zh" ? item.summary : "");
  const summaryEn = display.summary_en || (item.language === "en" ? item.summary : "");
  const titlePair = displayPair(titleZh, titleEn, item.title, item.language, "title");
  const summaryPair = displayPair(summaryZh, summaryEn, item.summary, item.language, "summary");
  return `
    <article class="intel-card">
      <div>
        <div class="meta-row">
          <span>${escapeHtml(item.platform || "unknown")}</span>
          <span>${escapeHtml(item.language || "unknown")}</span>
          <span>${escapeHtml(item.published_at || "")}</span>
          <span>${escapeHtml(item.translation_status || "untranslated")}</span>
        </div>
        ${bilingualTitleHtml(titlePair.original, titlePair.translation)}
        ${bilingualSummaryHtml(summaryPair.original, summaryPair.translation)}
        <div class="tag-row">
          <span class="tag">${escapeHtml(item.category || "general")}</span>
          ${signals.map((signal) => `<span class="tag ${tagClass(signal)}">${escapeHtml(signal)}</span>`).join("")}
        </div>
        ${intelligenceRiskHtml(item)}
        ${actionable ? actionHtml(item) : evidenceHtml(item)}
      </div>
      <div class="score" aria-label="权重 ${Number(item.score || 0)}">${Number(item.score || 0)}</div>
    </article>
  `;
}

function displayPair(zh, en, fallback, language, kind) {
  const waitingZh = kind === "title" ? "中文待 DeepSeek 翻译" : "中文摘要待 DeepSeek 翻译";
  const waitingEn = kind === "title" ? "English pending DeepSeek translation" : "English summary pending DeepSeek translation";
  if (language === "en") {
    return { original: en || fallback || "", translation: zh || waitingZh };
  }
  if (language === "zh") {
    return { original: zh || fallback || "", translation: en || waitingEn };
  }
  return { original: fallback || zh || en || "", translation: zh && en && zh !== en ? zh : waitingZh };
}

function bilingualTitleHtml(original, translation) {
  if (original && translation && original !== translation) {
    return `
      <h3 class="original-title">${escapeHtml(original)}</h3>
      <p class="translation-line">${escapeHtml(translation)}</p>
    `;
  }
  return `<h3 class="original-title">${escapeHtml(original || translation || "未命名情报")}</h3>`;
}

function bilingualSummaryHtml(original, translation) {
  if (original && translation && original !== translation) {
    return `
      <p class="original-summary">${escapeHtml(original)}</p>
      <p class="translation-line">${escapeHtml(translation)}</p>
    `;
  }
  return `<p class="original-summary">${escapeHtml(original || translation || "")}</p>`;
}

function intelligenceRiskHtml(item) {
  const cross = item.cross_check || {};
  const geo = item.geo_risk || {};
  const notes = item.advisor_notes || {};
  const reasons = Array.isArray(geo.reasons) ? geo.reasons.slice(0, 2).join("；") : "";
  const geoProbability = formatProbability(geo.probability, geo.level);
  return `
    <div class="intel-assessment">
      <span>交叉验证：${escapeHtml(cross.status || "unverified")}</span>
      <span>GEO：${escapeHtml(geo.level || "unknown")} · ${geoProbability}</span>
      ${notes.summary ? `<span>智库：${escapeHtml(notes.summary)}</span>` : ""}
      ${reasons ? `<span>原因：${escapeHtml(reasons)}</span>` : ""}
    </div>
  `;
}

function formatProbability(probability, level) {
  const numeric = Number(probability);
  if (Number.isFinite(numeric)) {
    return `${Math.round(numeric * 100)}%`;
  }
  const levelMap = { low: "20%", medium: "50%", high: "80%" };
  return levelMap[String(level || "").toLowerCase()] || "未知";
}

function actionHtml(item) {
  const id = escapeHtml(item.id);
  return `
    <div class="action-row">
      <label>
        <span class="sr-only">调整权重</span>
        <input data-weight-for="${id}" type="number" min="0" max="100" value="${Number(item.score || 0)}" />
      </label>
      <button type="button" data-decision="approved" data-id="${id}">确认</button>
      <button type="button" class="reject" data-decision="rejected" data-id="${id}">驳回</button>
      ${evidenceHtml(item)}
    </div>
  `;
}

function evidenceHtml(item) {
  const first = (item.evidence || [])[0];
  if (!first || !first.url) return "";
  return `<a href="${escapeAttribute(first.url)}" target="_blank" rel="noopener noreferrer">查看证据</a>`;
}

function bindDecisionButtons(root) {
  root.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => decide(button.dataset.id, button.dataset.decision));
  });
}

function tagClass(signal) {
  if (signal.includes("风险")) return "risk";
  if (signal.includes("外国")) return "foreign";
  return "";
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = String(value);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
