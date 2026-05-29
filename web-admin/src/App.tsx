import {
  Activity,
  ArchiveRestore,
  Bot,
  Boxes,
  Check,
  ClipboardCheck,
  Cloud,
  Database,
  FileJson,
  Gauge,
  Globe2,
  ListFilter,
  Play,
  Radar,
  RefreshCcw,
  ShieldAlert,
  SlidersHorizontal,
  Trash2,
  Video,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";

type ApiList<T> = { items?: T[]; empty_reason?: string; file?: string };
type AnyRecord = Record<string, any>;

type Summary = {
  version?: string;
  counts?: Record<string, number>;
  guardrails?: Record<string, boolean | string>;
};

type Config = {
  platforms: string[];
  manual_queries: string[];
  segments: string[];
  risk_terms: string[];
  opportunity_terms: string[];
  hermes_queries: string[];
  query_strategy: string;
  target_per_platform: number;
  title_target_per_platform: number;
  deep_process_limit_per_platform: number;
  freshness_window_hours: number;
  scroll_rounds_per_query: number;
  scroll_stop_after_no_new_rounds: number;
  wait_min_seconds: number;
  wait_max_seconds: number;
  max_items_per_task: number;
  detail_limit_per_task: number;
  video_processing_priority: string;
  enable_keyframes: boolean;
  asr_backend: string;
  asr_model: string;
  asr_language: string;
  cooldown_minutes_on_limit: number;
  quality_goal: string;
  parallel_limit: number;
  parallel_limit_warning?: boolean;
};

const defaultSummary: Summary = {
  version: "V0.2.4",
  counts: {
    candidates: 0,
    approved: 0,
    rejected: 0,
    pending: 0,
    risks: 0,
    opportunities: 0,
    foreign_signals: 0,
    geo_high: 0,
    jobs: 0,
    trash: 0
  },
  guardrails: {
    local_only: true,
    auto_review_not_auto_publish: true,
    trash_policy: "soft_delete_restore_14_days_no_batch_physical_delete"
  }
};

const defaultConfig: Config = {
  platforms: ["xiaohongshu", "douyin"],
  manual_queries: ["阳朔 旅游", "阳朔 竹筏", "阳朔 西街"],
  segments: ["景区", "民宿", "酒店", "旅游餐饮", "旅拍", "骑行", "亲子", "研学", "疗愈"],
  risk_terms: ["避雷", "排队", "投诉", "宰客", "堵车", "价格"],
  opportunity_terms: ["攻略", "路线", "新玩法", "小众", "体验", "vlog"],
  hermes_queries: [],
  query_strategy: "hybrid",
  target_per_platform: 200,
  title_target_per_platform: 200,
  deep_process_limit_per_platform: 40,
  freshness_window_hours: 24,
  scroll_rounds_per_query: 8,
  scroll_stop_after_no_new_rounds: 2,
  wait_min_seconds: 25,
  wait_max_seconds: 60,
  max_items_per_task: 20,
  detail_limit_per_task: 1,
  video_processing_priority: "asr",
  enable_keyframes: false,
  asr_backend: "auto",
  asr_model: "small",
  asr_language: "zh",
  cooldown_minutes_on_limit: 60,
  quality_goal: "v023_asr_first_title_pool",
  parallel_limit: 2
};

const nav = [
  ["采集作战台", Activity],
  ["采集配置", SlidersHorizontal],
  ["标题池", ListFilter],
  ["语音转文字深处理", Video],
  ["候选审阅", ClipboardCheck],
  ["交叉验证", ShieldAlert],
  ["生成式搜索风险", Radar],
  ["官方信源", Globe2],
  ["每日资料包", Boxes],
  ["证据保留", Database],
  ["云日志边界", Cloud],
  ["系统诊断", Gauge],
  ["后续智能体接口", FileJson],
  ["软删除回收站", Trash2],
  ["版本发布", ArchiveRestore]
] as const;

const stageLabels: Record<string, string> = {
  titles: "采集标题池",
  screen: "机会风险初筛",
  videos: "视频语音处理",
  all: "完整采集流程"
};

const platformLabels: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  wechat_channels: "视频号"
};

async function getJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url);
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

function unwrapItems<T>(payload: ApiList<T> | T[] | undefined): T[] {
  if (Array.isArray(payload)) return payload;
  return payload?.items || [];
}

function getTitle(item: AnyRecord): string {
  return item.title || item.display?.title_zh || item.display?.title || item.claim || item.topic || item.id || "未命名条目";
}

function getSummary(item: AnyRecord): string {
  return item.summary || item.display?.summary_zh || item.text || item.description || "暂无摘要";
}

export default function App() {
  const [activePage, setActivePage] = useState("采集作战台");
  const [summary, setSummary] = useState<Summary>(defaultSummary);
  const [config, setConfig] = useState<Config>(defaultConfig);
  const [editConfig, setEditConfig] = useState<Config>(defaultConfig);
  const [jobs, setJobs] = useState<AnyRecord[]>([]);
  const [jobLog, setJobLog] = useState("");
  const [titles, setTitles] = useState<AnyRecord[]>([]);
  const [titleMeta, setTitleMeta] = useState<ApiList<AnyRecord>>({});
  const [videos, setVideos] = useState<AnyRecord[]>([]);
  const [videoMeta, setVideoMeta] = useState<ApiList<AnyRecord>>({});
  const [candidates, setCandidates] = useState<AnyRecord[]>([]);
  const [officialSources, setOfficialSources] = useState<AnyRecord[]>([]);
  const [dailyBundles, setDailyBundles] = useState<AnyRecord[]>([]);
  const [cloudLogs, setCloudLogs] = useState<AnyRecord[]>([]);
  const [trash, setTrash] = useState<AnyRecord[]>([]);
  const [selectedTrashIds, setSelectedTrashIds] = useState<string[]>([]);
  const [agentApis, setAgentApis] = useState<AnyRecord[]>([]);
  const [releaseStatus, setReleaseStatus] = useState<AnyRecord>({});
  const [retention, setRetention] = useState({ evidence_hours: 48, cloud_log_months: 3, notice: "" });
  const [diagnosis, setDiagnosis] = useState<AnyRecord | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState("xiaohongshu");
  const [toast, setToast] = useState("");
  const [newTerm, setNewTerm] = useState<Record<string, string>>({});
  const [newSource, setNewSource] = useState({ label: "", url: "", mission_id: "yangshuo", recommended_by: "manual" });
  const [saving, setSaving] = useState(false);

  const counts = summary.counts || defaultSummary.counts || {};

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    setEditConfig({ ...defaultConfig, ...config });
  }, [config]);

  useEffect(() => {
    const hasRunningJob = jobs.some((job) => ["queued", "running"].includes(String(job.status)));
    if (!hasRunningJob) return;
    const timer = window.setInterval(() => {
      void fetchJobs();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [jobs]);

  async function refreshAll() {
    const [
      nextSummary,
      nextConfig,
      nextJobs,
      titlePayload,
      videoPayload,
      candidatePayload,
      officialPayload,
      bundlePayload,
      cloudPayload,
      trashPayload,
      apiPayload,
      releasePayload,
      retentionPayload
    ] = await Promise.all([
      getJson<Summary>("/api/v1/dashboard/summary", defaultSummary),
      getJson<Config>("/api/v1/collection/config", defaultConfig),
      getJson<ApiList<AnyRecord>>("/api/v1/collection/jobs", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/title-pool", { items: [], empty_reason: "未连接后台接口" }),
      getJson<ApiList<AnyRecord>>("/api/v1/video-processing", { items: [], empty_reason: "未连接后台接口" }),
      getJson<ApiList<AnyRecord>>("/api/v1/intelligence/candidates", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/admin/official-sources", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/daily-bundles", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/cloud-log-syncs", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/trash", { items: [] }),
      getJson<ApiList<AnyRecord>>("/api/v1/agent/apis", { items: [] }),
      getJson<AnyRecord>("/api/v1/release/status", {}),
      getJson<any>("/api/v1/admin/retention", { evidence_hours: 48, cloud_log_months: 3, notice: "" })
    ]);

    setSummary(nextSummary);
    setConfig({ ...defaultConfig, ...nextConfig });
    setJobs(unwrapItems(nextJobs));
    setTitleMeta(titlePayload);
    setTitles(unwrapItems(titlePayload));
    setVideoMeta(videoPayload);
    setVideos(unwrapItems(videoPayload));
    setCandidates(unwrapItems(candidatePayload));
    setOfficialSources(unwrapItems(officialPayload));
    setDailyBundles(unwrapItems(bundlePayload));
    setCloudLogs(unwrapItems(cloudPayload));
    setTrash(unwrapItems(trashPayload));
    setAgentApis(unwrapItems(apiPayload));
    setReleaseStatus(releasePayload || {});
    setRetention({
      evidence_hours: retentionPayload.evidence_hours ?? 48,
      cloud_log_months: retentionPayload.cloud_log_months ?? 3,
      notice: retentionPayload.notice || ""
    });
  }

  async function fetchJobs() {
    const payload = await getJson<ApiList<AnyRecord>>("/api/v1/collection/jobs", { items: [] });
    setJobs(unwrapItems(payload));
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  }

  async function startJob(stage: string) {
    if (!dryRun) {
      const ok = window.confirm(
        `你将真实启动 ${platformLabels[selectedPlatform] || selectedPlatform} 的“${stageLabels[stage]}”。\n这会调用本机 OpenCLI 和平台登录态。确认继续吗？`
      );
      if (!ok) return;
    }
    const response = await fetch("/api/v1/collection/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: selectedPlatform, stage, dry_run: dryRun })
    });
    if (!response.ok) {
      showToast("任务提交失败，请到系统诊断查看 OpenCLI 和后台状态");
      return;
    }
    const job = await response.json();
    setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
    showToast(`已提交任务：${stageLabels[stage]}，任务号 ${job.id}`);
    void fetchJobLog(job.id);
  }

  async function fetchJobLog(jobId: string) {
    try {
      const response = await fetch(`/api/v1/collection/jobs/${jobId}/log`);
      setJobLog(response.ok ? await response.text() : "");
    } catch {
      setJobLog("");
    }
  }

  async function cancelJob(jobId: string) {
    const ok = window.confirm(`确认停止任务 ${jobId} 吗？\n停止后后台会向采集进程发送正常终止信号，并保留日志。`);
    if (!ok) return;
    const response = await fetch(`/api/v1/collection/jobs/${jobId}/cancel`, { method: "POST" });
    if (!response.ok) {
      showToast("停止任务失败，请刷新后检查任务状态");
      return;
    }
    const payload = await response.json();
    if (payload.job) {
      setJobs((prev) => prev.map((item) => (item.id === jobId ? payload.job : item)));
    }
    showToast(`已发送停止请求：${jobId}`);
    void fetchJobs();
    void fetchJobLog(jobId);
  }

  async function saveConfig(event: React.FormEvent) {
    event.preventDefault();
    if (editConfig.parallel_limit > 2) {
      const ok = window.confirm(`当前并发上限是 ${editConfig.parallel_limit}，超过保守默认值 2。确认保存吗？`);
      if (!ok) return;
    }
    setSaving(true);
    const response = await fetch("/api/v1/collection/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editConfig)
    });
    setSaving(false);
    if (!response.ok) {
      showToast("配置保存失败，未写入 config/live_collect.json");
      return;
    }
    const saved = await response.json();
    setConfig({ ...defaultConfig, ...saved });
    showToast("配置已保存，并同步写入 config/live_collect.json");
  }

  async function postDecision(id: string, status: "approved" | "rejected") {
    const response = await fetch("/api/v1/intelligence/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, status })
    });
    if (!response.ok) {
      showToast("审阅操作失败");
      return;
    }
    showToast(status === "approved" ? "已确认候选情报" : "已驳回候选情报");
    void refreshAll();
  }

  async function moveCandidateToTrash(id: string) {
    const response = await fetch("/api/v1/trash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_type: "candidate", ids: [id], reason: "后台人工软删除" })
    });
    showToast(response.ok ? "已移入软删除回收站" : "移入回收站失败");
    void refreshAll();
  }

  async function restoreTrash() {
    const response = await fetch("/api/v1/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: selectedTrashIds })
    });
    showToast(response.ok ? "已恢复所选条目" : "恢复失败");
    setSelectedTrashIds([]);
    void refreshAll();
  }

  async function markTrashCleanable() {
    const response = await fetch("/api/v1/trash/mark-cleanable", { method: "POST" });
    showToast(response.ok ? "已标记 14 天后可清理；未物理删除文件" : "标记失败");
    void refreshAll();
  }

  async function saveRetention(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch("/api/v1/admin/retention", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(retention)
    });
    showToast(response.ok ? "证据保留设置已保存" : "证据保留设置保存失败");
    void refreshAll();
  }

  async function saveOfficialSource(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch("/api/v1/admin/official-sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...newSource, id: newSource.url || crypto.randomUUID(), status: "active" })
    });
    if (!response.ok) {
      showToast("官方信源保存失败");
      return;
    }
    setNewSource({ label: "", url: "", mission_id: "yangshuo", recommended_by: "manual" });
    showToast("官方信源已保存");
    void refreshAll();
  }

  async function runDiagnosis() {
    setDiagnosis({ running: true });
    const payload = await getJson<AnyRecord>("/api/v1/system/diagnose", { ok: false, error: "诊断接口不可用" });
    setDiagnosis(payload);
  }

  function addArrayValue(key: keyof Config) {
    const value = (newTerm[String(key)] || "").trim();
    if (!value) return;
    const current = Array.isArray(editConfig[key]) ? (editConfig[key] as string[]) : [];
    setEditConfig({ ...editConfig, [key]: [...current, value] });
    setNewTerm({ ...newTerm, [String(key)]: "" });
  }

  function removeArrayValue(key: keyof Config, index: number) {
    const current = Array.isArray(editConfig[key]) ? (editConfig[key] as string[]) : [];
    setEditConfig({ ...editConfig, [key]: current.filter((_, itemIndex) => itemIndex !== index) });
  }

  const crossCheckItems = useMemo(
    () => candidates.filter((item) => item.cross_check || item.claim || item.support_sources || item.conflict_sources),
    [candidates]
  );
  const geoRiskItems = useMemo(
    () => candidates.filter((item) => item.geo_risk || item.geo_risk_score || item.geo_risk_probability),
    [candidates]
  );

  return (
    <div className="min-h-dvh bg-background text-foreground lg:flex">
      <aside className="border-b border-border bg-card px-4 py-4 lg:sticky lg:top-0 lg:h-dvh lg:w-72 lg:border-b-0 lg:border-r">
        <div className="mb-4 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-primary text-sm font-black text-primary-foreground">AF</div>
          <div>
            <p className="text-sm font-bold">以太通量后台</p>
            <p className="text-xs text-muted-foreground">AetherFlux · {summary.version || "V0.2.4"}</p>
          </div>
        </div>
        <nav className="grid max-h-[42vh] gap-1 overflow-y-auto pr-1 sm:grid-cols-2 lg:max-h-[calc(100vh-96px)] lg:grid-cols-1">
          {nav.map(([label, Icon]) => (
            <button
              key={label}
              onClick={() => setActivePage(label)}
              className={`flex min-h-10 items-center gap-3 rounded-md px-3 text-left text-sm font-medium transition ${
                activePage === label ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground">V0.2.4 后台控制台</p>
              <h1 className="text-2xl font-black tracking-normal">以太情报后台</h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="success">本机免登录</Badge>
              <Badge tone="warning">自动审议，不自动发布</Badge>
              <Badge tone="info">127.0.0.1</Badge>
            </div>
          </div>
        </header>

        {toast && <div className="mx-4 mt-4 rounded-md border border-border bg-card px-4 py-3 text-sm md:mx-6">{toast}</div>}

        <div className="space-y-6 p-4 md:p-6">
          {activePage === "采集作战台" && (
            <Page title="采集作战台" icon={<Activity className="h-5 w-5" />}>
              <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                <Card>
                  <CardHeader>
                    <CardTitle>启动真实采集流程</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="目标平台">
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(platformLabels).map(([key, label]) => (
                            <Button key={key} variant={selectedPlatform === key ? "primary" : "secondary"} onClick={() => setSelectedPlatform(key)}>
                              {label}
                            </Button>
                          ))}
                        </div>
                      </Field>
                      <Field label="运行模式">
                        <div className="flex flex-wrap gap-2">
                          <Button variant={dryRun ? "primary" : "secondary"} onClick={() => setDryRun(true)}>Dry-run</Button>
                          <Button variant={!dryRun ? "danger" : "secondary"} onClick={() => setDryRun(false)}>真实运行</Button>
                        </div>
                      </Field>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {Object.entries(stageLabels).map(([stage, label]) => (
                        <button key={stage} onClick={() => void startJob(stage)} className="rounded-md border border-border bg-card p-4 text-left transition hover:border-primary">
                          <div className="flex items-center justify-between gap-3">
                            <strong>{label}</strong>
                            <Play className="h-4 w-4 text-primary" />
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">使用当前配置快照提交任务，后台记录命令、退出码和日志。</p>
                        </button>
                      ))}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Metric label="标题池目标/平台" value={config.title_target_per_platform} />
                      <Metric label="深处理上限/平台" value={config.deep_process_limit_per_platform} />
                      <Metric label="并发上限" value={config.parallel_limit} tone={config.parallel_limit > 2 ? "warning" : "neutral"} />
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle>任务队列与日志</CardTitle>
                      <Button variant="secondary" onClick={() => void fetchJobs()}><RefreshCcw className="h-4 w-4" />刷新</Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <DataTable
                      items={jobs}
                      empty="暂无采集任务。先在左侧选择阶段启动 dry-run 或真实运行。"
                      columns={[
                        ["任务", (job) => <button className="font-mono text-primary hover:underline" onClick={() => void fetchJobLog(job.id)}>{job.id}</button>],
                        ["平台", (job) => platformLabels[job.platform] || job.platform],
                        ["阶段", (job) => stageLabels[job.stage] || job.stage],
                        ["状态", (job) => <StatusBadge status={job.status} />],
                        ["操作", (job) => ["queued", "running", "cancelling"].includes(String(job.status)) ? (
                          <Button variant="danger" onClick={() => void cancelJob(job.id)}>停止</Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">无需操作</span>
                        )]
                      ]}
                    />
                    <pre className="max-h-64 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{jobLog || "点击任务 ID 查看日志；真实失败时这里会显示 OpenCLI、登录态、平台限制或依赖错误。"}</pre>
                  </CardContent>
                </Card>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="候选情报" value={counts.candidates || 0} />
                <Metric label="已确认" value={counts.approved || 0} tone="success" />
                <Metric label="风险预警" value={counts.risks || 0} tone="danger" />
                <Metric label="生成式搜索高疑似" value={counts.geo_high || 0} tone="warning" />
              </div>
            </Page>
          )}

          {activePage === "采集配置" && (
            <Page title="采集配置" icon={<SlidersHorizontal className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>写入 config/live_collect.json</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={saveConfig} className="space-y-6">
                    <div className="grid gap-5 lg:grid-cols-2">
                      <ArrayEditor label="平台" field="platforms" values={editConfig.platforms} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                      <ArrayEditor label="关键词" field="manual_queries" values={editConfig.manual_queries} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                      <ArrayEditor label="细分赛道" field="segments" values={editConfig.segments} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                      <ArrayEditor label="风险词" field="risk_terms" values={editConfig.risk_terms} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                      <ArrayEditor label="机会词" field="opportunity_terms" values={editConfig.opportunity_terms} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                      <ArrayEditor label="Hermes 探索词" field="hermes_queries" values={editConfig.hermes_queries} onAdd={addArrayValue} onRemove={removeArrayValue} newTerm={newTerm} setNewTerm={setNewTerm} />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <NumberInput label="标题池目标" value={editConfig.title_target_per_platform} onChange={(v) => setEditConfig({ ...editConfig, title_target_per_platform: v, target_per_platform: v })} />
                      <NumberInput label="深处理上限" value={editConfig.deep_process_limit_per_platform} onChange={(v) => setEditConfig({ ...editConfig, deep_process_limit_per_platform: v })} />
                      <NumberInput label="新鲜度窗口小时" value={editConfig.freshness_window_hours} onChange={(v) => setEditConfig({ ...editConfig, freshness_window_hours: v })} />
                      <NumberInput label="滚动轮数" value={editConfig.scroll_rounds_per_query} onChange={(v) => setEditConfig({ ...editConfig, scroll_rounds_per_query: v })} />
                      <NumberInput label="等待最小秒" value={editConfig.wait_min_seconds} onChange={(v) => setEditConfig({ ...editConfig, wait_min_seconds: v })} />
                      <NumberInput label="等待最大秒" value={editConfig.wait_max_seconds} onChange={(v) => setEditConfig({ ...editConfig, wait_max_seconds: v })} />
                      <NumberInput label="冷却分钟" value={editConfig.cooldown_minutes_on_limit} onChange={(v) => setEditConfig({ ...editConfig, cooldown_minutes_on_limit: v })} />
                      <NumberInput label="并发上限" value={editConfig.parallel_limit} onChange={(v) => setEditConfig({ ...editConfig, parallel_limit: v })} />
                      <NumberInput label="无新增停止轮数" value={editConfig.scroll_stop_after_no_new_rounds} onChange={(v) => setEditConfig({ ...editConfig, scroll_stop_after_no_new_rounds: v })} />
                      <NumberInput label="任务最大条数" value={editConfig.max_items_per_task} onChange={(v) => setEditConfig({ ...editConfig, max_items_per_task: v })} />
                      <NumberInput label="详情抓取上限" value={editConfig.detail_limit_per_task} onChange={(v) => setEditConfig({ ...editConfig, detail_limit_per_task: v })} />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <TextInput label="ASR 后端" value={editConfig.asr_backend} onChange={(v) => setEditConfig({ ...editConfig, asr_backend: v })} />
                      <TextInput label="ASR 模型" value={editConfig.asr_model} onChange={(v) => setEditConfig({ ...editConfig, asr_model: v })} />
                      <TextInput label="ASR 语言" value={editConfig.asr_language} onChange={(v) => setEditConfig({ ...editConfig, asr_language: v })} />
                      <TextInput label="质量目标" value={editConfig.quality_goal} onChange={(v) => setEditConfig({ ...editConfig, quality_goal: v })} />
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={editConfig.enable_keyframes} onChange={(event) => setEditConfig({ ...editConfig, enable_keyframes: event.target.checked })} />
                      开启抽帧；默认关闭，ASR 优先
                    </label>
                    <Button type="submit" disabled={saving}>{saving ? "保存中..." : "保存配置"}</Button>
                  </form>
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "标题池" && (
            <Page title="标题池" icon={<ListFilter className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>最新标题池文件{titleMeta.file ? `：${titleMeta.file}` : ""}</CardTitle></CardHeader>
                <CardContent>
                  <DataTable
                    items={titles}
                    empty={`暂无标题池数据。${titleMeta.empty_reason || "先在采集作战台运行 titles 阶段。"}`}
                    columns={[
                      ["标题", (item) => getTitle(item)],
                      ["平台", (item) => platformLabels[item.platform] || item.platform || "-"],
                      ["关键词", (item) => item.query || item.keyword || "-"],
                      ["状态", (item) => item.status || item.quality_status || "待处理"],
                      ["操作", (item) => <Button variant="secondary" onClick={() => showToast(`已记录操作意图：${getTitle(item)}`)}>强制深处理/排除</Button>]
                    ]}
                  />
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "语音转文字深处理" && (
            <Page title="语音转文字深处理" icon={<Video className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>ASR 深处理结果{videoMeta.file ? `：${videoMeta.file}` : ""}</CardTitle></CardHeader>
                <CardContent>
                  <DataTable
                    items={videos}
                    empty={`暂无 ASR 结果。${videoMeta.empty_reason || "先运行 videos 阶段。"}`}
                    columns={[
                      ["标题", (item) => getTitle(item)],
                      ["下载", (item) => item.download_status || item.download?.status || "-"],
                      ["ASR", (item) => item.asr_status || item.status || "-"],
                      ["摘要", (item) => getSummary(item)],
                      ["失败原因", (item) => item.error || item.error_summary || "-"]
                    ]}
                  />
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "候选审阅" && (
            <Page title="候选审阅" icon={<ClipboardCheck className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>待人工确认候选</CardTitle></CardHeader>
                <CardContent>
                  <DataTable
                    items={candidates}
                    empty="暂无候选情报。先运行采集与审议流程。"
                    columns={[
                      ["标题", (item) => <div><strong>{getTitle(item)}</strong><p className="text-xs text-muted-foreground">{getSummary(item)}</p></div>],
                      ["平台", (item) => platformLabels[item.platform] || item.platform || "-"],
                      ["状态", (item) => item.human_status || item.status || "pending"],
                      ["分数", (item) => item.score ?? item.weight ?? "-"],
                      ["操作", (item) => <div className="flex flex-wrap gap-2"><Button onClick={() => void postDecision(item.id, "approved")}><Check className="h-4 w-4" />确认</Button><Button variant="danger" onClick={() => void postDecision(item.id, "rejected")}><X className="h-4 w-4" />驳回</Button><Button variant="secondary" onClick={() => void moveCandidateToTrash(item.id)}>软删除</Button></div>]
                    ]}
                  />
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "交叉验证" && (
            <Page title="交叉验证" icon={<ShieldAlert className="h-5 w-5" />}>
              <RecordCards items={crossCheckItems} empty="暂无交叉验证数据。候选条目生成 cross_check 后会显示 claim、支持来源、冲突来源和补证建议。" render={(item) => (
                <>
                  <h3 className="font-semibold">{item.claim || getTitle(item)}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{JSON.stringify(item.cross_check || item.support_sources || item.conflict_sources || {}, null, 2)}</p>
                </>
              )} />
            </Page>
          )}

          {activePage === "生成式搜索风险" && (
            <Page title="生成式搜索风险" icon={<Radar className="h-5 w-5" />}>
              <p className="text-sm text-muted-foreground">这里只表达疑似度和风险概率，不做事实定罪。</p>
              <RecordCards items={geoRiskItems} empty="暂无 GEO 风险数据。候选条目生成 geo_risk 后会显示概率、等级、原因和人工备注入口。" render={(item) => {
                const risk = item.geo_risk || {};
                return (
                  <>
                    <h3 className="font-semibold">{getTitle(item)}</h3>
                    <p className="mt-2 text-sm">概率：{risk.probability ?? item.geo_risk_score ?? "-"}；等级：{risk.level ?? "-"}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{Array.isArray(risk.reasons) ? risk.reasons.join("；") : risk.reasons || "暂无原因"}</p>
                  </>
                );
              }} />
            </Page>
          )}

          {activePage === "官方信源" && (
            <Page title="官方信源" icon={<Globe2 className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>新增或编辑官方信源</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={saveOfficialSource} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
                    <TextInput label="名称" value={newSource.label} onChange={(v) => setNewSource({ ...newSource, label: v })} />
                    <TextInput label="URL" value={newSource.url} onChange={(v) => setNewSource({ ...newSource, url: v })} />
                    <TextInput label="mission" value={newSource.mission_id} onChange={(v) => setNewSource({ ...newSource, mission_id: v })} />
                    <div className="flex items-end"><Button type="submit">保存</Button></div>
                  </form>
                </CardContent>
              </Card>
              <DataTable
                items={officialSources}
                empty="暂无官方信源。请先新增阳朔政府、景区、交通、气象或 OTA 官方 URL。"
                columns={[
                  ["名称", (item) => item.label || item.name || "-"],
                  ["URL", (item) => item.url || "-"],
                  ["mission", (item) => item.mission_id || "-"],
                  ["状态", (item) => item.status || "needs_review"]
                ]}
              />
            </Page>
          )}

          {activePage === "每日资料包" && <SimpleTablePage title="每日资料包" icon={<Boxes className="h-5 w-5" />} items={dailyBundles} empty="暂无每日资料包记录。" />}

          {activePage === "证据保留" && (
            <Page title="证据保留" icon={<Database className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>本地证据与云日志保留</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={saveRetention} className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <NumberInput label="本地证据保留小时" value={retention.evidence_hours} onChange={(v) => setRetention({ ...retention, evidence_hours: v })} />
                      <NumberInput label="云日志索引保留月数" value={retention.cloud_log_months} onChange={(v) => setRetention({ ...retention, cloud_log_months: v })} />
                    </div>
                    <p className="rounded-md border border-border bg-muted p-3 text-sm text-muted-foreground">{retention.notice || "原始截图、HTML、音视频、评论全文和完整转写不上传 Supabase Cloud。"}</p>
                    <Button type="submit">保存保留设置</Button>
                  </form>
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "云日志边界" && <SimpleTablePage title="云日志边界" icon={<Cloud className="h-5 w-5" />} items={cloudLogs} empty="暂无 Supabase 轻量日志同步记录；不会展示 service key、cookie 或 token。" />}

          {activePage === "系统诊断" && (
            <Page title="系统诊断" icon={<Gauge className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>DeepSeek / OpenCLI / ASR 环境</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <Button onClick={() => void runDiagnosis()}><RefreshCcw className="h-4 w-4" />运行诊断</Button>
                  <pre className="max-h-[480px] overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-100">{diagnosis ? JSON.stringify(diagnosis, null, 2) : "尚未运行诊断。"}</pre>
                </CardContent>
              </Card>
            </Page>
          )}

          {activePage === "后续智能体接口" && <SimpleTablePage title="后续智能体接口" icon={<Bot className="h-5 w-5" />} items={agentApis} empty="暂无接口索引。" />}

          {activePage === "软删除回收站" && (
            <Page title="软删除回收站" icon={<Trash2 className="h-5 w-5" />}>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={selectedTrashIds.length === 0} onClick={() => void restoreTrash()}>恢复所选</Button>
                <Button variant="secondary" onClick={() => void markTrashCleanable()}>标记可清理</Button>
              </div>
              <DataTable
                items={trash}
                empty="回收站为空。这里仅做软删除恢复和可清理标记，不物理批量删除文件。"
                columns={[
                  ["选择", (item) => <input type="checkbox" checked={selectedTrashIds.includes(item.id)} onChange={() => setSelectedTrashIds((prev) => prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id])} />],
                  ["标题", (item) => getTitle(item)],
                  ["类型", (item) => item.item_type || "-"],
                  ["可清理", (item) => item.cleanable ? "是" : "否"],
                  ["恢复期限", (item) => item.restore_until || "-"]
                ]}
              />
            </Page>
          )}

          {activePage === "版本发布" && (
            <Page title="版本发布" icon={<ArchiveRestore className="h-5 w-5" />}>
              <Card>
                <CardHeader><CardTitle>{releaseStatus.version || "V0.2.4"}</CardTitle></CardHeader>
                <CardContent>
                  <ul className="grid gap-2 text-sm">
                    {(releaseStatus.checklist || []).map((item: string) => <li key={item} className="rounded-md border border-border p-3">{item}</li>)}
                  </ul>
                </CardContent>
              </Card>
            </Page>
          )}
        </div>
      </main>
    </div>
  );
}

function Page({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="text-primary">{icon}</div>
        <h2 className="text-xl font-bold tracking-normal">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: number | string; tone?: "neutral" | "success" | "warning" | "danger" }) {
  const toneClass = tone === "success" ? "text-emerald-600" : tone === "warning" ? "text-amber-600" : tone === "danger" ? "text-rose-600" : "text-foreground";
  return (
    <Card>
      <CardContent>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={`mt-1 text-2xl font-bold ${toneClass}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status?: string }) {
  const value = status || "unknown";
  const tone = ["succeeded", "completed", "approved", "ok"].includes(value) ? "success" : ["failed", "rejected"].includes(value) ? "danger" : "warning";
  return <Badge tone={tone as any}>{value}</Badge>;
}

function DataTable({ items, empty, columns }: { items: AnyRecord[]; empty: string; columns: [string, (item: AnyRecord) => React.ReactNode][] }) {
  if (!items.length) return <EmptyState text={empty} />;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-muted text-xs text-muted-foreground">
          <tr>{columns.map(([label]) => <th key={label} className="px-3 py-2 font-semibold">{label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item, index) => (
            <tr key={item.id || index} className="align-top">
              {columns.map(([label, render]) => <td key={label} className="px-3 py-3">{render(item)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-border bg-muted/40 p-8 text-center text-sm text-muted-foreground">{text}</div>;
}

function ArrayEditor({ label, field, values, newTerm, setNewTerm, onAdd, onRemove }: {
  label: string;
  field: keyof Config;
  values: string[];
  newTerm: Record<string, string>;
  setNewTerm: (value: Record<string, string>) => void;
  onAdd: (field: keyof Config) => void;
  onRemove: (field: keyof Config, index: number) => void;
}) {
  return (
    <div className="space-y-3 rounded-md border border-border p-4">
      <p className="text-sm font-semibold">{label}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((value, index) => (
          <Badge key={`${value}-${index}`} tone="neutral">
            {value}
            <button type="button" className="ml-1" onClick={() => onRemove(field, index)}>×</button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <input className="min-h-10 flex-1 rounded-md border border-border bg-background px-3 text-sm" value={newTerm[String(field)] || ""} onChange={(event) => setNewTerm({ ...newTerm, [String(field)]: event.target.value })} />
        <Button type="button" variant="secondary" onClick={() => onAdd(field)}>添加</Button>
      </div>
    </div>
  );
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="space-y-2">
      <span className="block text-xs font-semibold text-muted-foreground">{label}</span>
      <input className="min-h-10 w-full rounded-md border border-border bg-background px-3 text-sm" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2">
      <span className="block text-xs font-semibold text-muted-foreground">{label}</span>
      <input className="min-h-10 w-full rounded-md border border-border bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function RecordCards({ items, empty, render }: { items: AnyRecord[]; empty: string; render: (item: AnyRecord) => React.ReactNode }) {
  if (!items.length) return <EmptyState text={empty} />;
  return <div className="grid gap-3">{items.map((item, index) => <Card key={item.id || index}><CardContent>{render(item)}</CardContent></Card>)}</div>;
}

function SimpleTablePage({ title, icon, items, empty }: { title: string; icon: React.ReactNode; items: AnyRecord[]; empty: string }) {
  const keys = Array.from(new Set(items.flatMap((item) => Object.keys(item)))).slice(0, 6);
  return (
    <Page title={title} icon={icon}>
      <DataTable
        items={items}
        empty={empty}
        columns={(keys.length ? keys : ["id", "status"]).map((key) => [key, (item: AnyRecord) => String(item[key] ?? "-")] as [string, (item: AnyRecord) => React.ReactNode])}
      />
    </Page>
  );
}
