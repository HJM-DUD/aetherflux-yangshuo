const state = {
  candidates: [],
  selected: [],
  foreign: [],
  opportunities: [],
  risks: [],
  draft: null,
};

const endpoints = {
  candidates: "/api/candidates",
  selected: "/api/selected",
  foreign: "/api/foreign-signals",
  opportunities: "/api/opportunities",
  risks: "/api/risks",
  draft: "/api/review-drafts/latest",
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("runIngest").addEventListener("click", runIngest);
  document.getElementById("runReview").addEventListener("click", runReview);
  refreshAll();
});

async function refreshAll() {
  const [candidates, selected, foreign, opportunities, risks, draft] = await Promise.all([
    getJson(endpoints.candidates),
    getJson(endpoints.selected),
    getJson(endpoints.foreign),
    getJson(endpoints.opportunities),
    getJson(endpoints.risks),
    getJson(endpoints.draft),
  ]);
  state.candidates = candidates.items || [];
  state.selected = selected.items || [];
  state.foreign = foreign.items || [];
  state.opportunities = opportunities.items || [];
  state.risks = risks.items || [];
  state.draft = draft || {};
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
  renderDraft();
  renderList("selectedList", state.selected, false);
  renderList("foreignList", state.foreign, true);
  renderList("opportunityList", state.opportunities, true);
  renderList("riskList", state.risks, false);
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
  return `
    <article class="intel-card">
      <div>
        <div class="meta-row">
          <span>${escapeHtml(item.platform || "unknown")}</span>
          <span>${escapeHtml(item.language || "unknown")}</span>
          <span>${escapeHtml(item.published_at || "")}</span>
        </div>
        <h3>${escapeHtml(item.title || "未命名情报")}</h3>
        <p>${escapeHtml(item.summary || "")}</p>
        <div class="tag-row">
          <span class="tag">${escapeHtml(item.category || "general")}</span>
          ${signals.map((signal) => `<span class="tag ${tagClass(signal)}">${escapeHtml(signal)}</span>`).join("")}
        </div>
        ${actionable ? actionHtml(item) : evidenceHtml(item)}
      </div>
      <div class="score" aria-label="权重 ${Number(item.score || 0)}">${Number(item.score || 0)}</div>
    </article>
  `;
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
