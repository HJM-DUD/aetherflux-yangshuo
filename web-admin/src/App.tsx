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
  Monitor,
  Moon,
  Play,
  Radar,
  RefreshCcw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Sun,
  Trash2,
  Video,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";

type ApiList<T> = { items?: T[]; empty_reason?: string; file?: string; collected_at?: string };
type AnyRecord = Record<string, any>;
type ThemeMode = "system" | "light" | "dark";

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
  ["采集操作台", Activity],
  ["采集配置", SlidersHorizontal],
  ["标题池", ListFilter],
  ["语音转文字深处理", Video],
  ["候选审阅", ClipboardCheck],
  ["交叉验证", ShieldAlert],
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

const jobPageSize = 8;
const themeStorageKey = "aetherflux-admin-theme";

const statusLabels: Record<string, string> = {
  queued: "等待中",
  running: "运行中",
  cancelling: "正在停止",
  cancelled: "已停止",
  succeeded: "已完成",
  completed: "已完成",
  failed: "失败",
  pending: "待确认",
  rejected: "已驳回",
  approved: "已确认",
  deleted: "已软删除",
  ok: "正常",
  unknown: "未知"
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

function getTitleSearchText(item: AnyRecord): string {
  return [
    getTitle(item),
    getSummary(item),
    item.platform,
    item.query,
    item.keyword,
    item.status,
    item.quality_status,
    item.id,
    item.url,
    item.source_url,
    item.author,
    item.account,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function formatDateTime(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

function getInitialThemeMode(): ThemeMode {
  if (typeof window === "undefined") return "system";
  const saved = window.localStorage.getItem(themeStorageKey);
  return saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
}

function formatPlatform(platform?: string): string {
  const value = platform || "-";
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => platformLabels[item] || item)
    .join("、") || "-";
}

export default function App() {
  const [activePage, setActivePage] = useState("采集操作台");
  const [summary, setSummary] = useState<Summary>(defaultSummary);
  const [config, setConfig] = useState<Config>(defaultConfig);
  const [editConfig, setEditConfig] = useState<Config>(defaultConfig);
  const [jobs, setJobs] = useState<AnyRecord[]>([]);
  const [jobLog, setJobLog] = useState("");
  const [titles, setTitles] = useState<AnyRecord[]>([]);
  const [titleMeta, setTitleMeta] = useState<ApiList<AnyRecord>>({});
  const [titleSearch, setTitleSearch] = useState("");
  const [videos, setVideos] = useState<AnyRecord[]>([]);
  const [videoMeta, setVideoMeta] = useState<ApiList<AnyRecord>>({});
  const [candidates, setCandidates] = useState<AnyRecord[]>([]);
  const [officialSources, setOfficialSources] = useState<AnyRecord[]>([]);
  const [dailyBundles, setDailyBundles] = useState<AnyRecord[]>([]);
  const [cloudLogs, setCloudLogs] = useState<AnyRecord[]>([]);
  const [trash, setTrash] = useState<AnyRecord[]>([]);
  const [locallyDeletedCandidateIds, setLocallyDeletedCandidateIds] = useState<string[]>([]);
  const [selectedTrashIds, setSelectedTrashIds] = useState<string[]>([]);
  const [agentApis, setAgentApis] = useState<AnyRecord[]>([]);
  const [releaseStatus, setReleaseStatus] = useState<AnyRecord>({});
  const [retention, setRetention] = useState({ evidence_hours: 48, cloud_log_months: 3, notice: "" });
  const [diagnosis, setDiagnosis] = useState<AnyRecord | null>(null);
  const [toast, setToast] = useState("");
  const [selectedJobId, setSelectedJobId] = useState("");
  const [jobPage, setJobPage] = useState(1);
  const [jobsRefreshedAt, setJobsRefreshedAt] = useState("");
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialThemeMode);
  const [newTerm, setNewTerm] = useState<Record<string, string>>({});
  const [newSource, setNewSource] = useState({ label: "", url: "", mission_id: "yangshuo", recommended_by: "manual" });
  const [saving, setSaving] = useState(false);

  const counts = summary.counts || defaultSummary.counts || {};

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolved = themeMode === "system" ? (media?.matches ? "dark" : "light") : themeMode;
      root.dataset.theme = resolved;
      root.dataset.themeMode = themeMode;
      root.classList.toggle("dark", resolved === "dark");
      window.localStorage.setItem(themeStorageKey, themeMode);
    };
    applyTheme();
    if (themeMode !== "system" || !media) return;
    media.addEventListener?.("change", applyTheme);
    return () => media.removeEventListener?.("change", applyTheme);
  }, [themeMode]);

  useEffect(() => {
    setEditConfig({ ...defaultConfig, ...config });
  }, [config]);

  useEffect(() => {
    if (activePage !== "采集操作台") return;
    const timer = window.setInterval(() => {
      void fetchJobs();
      if (selectedJobId) void fetchJobLog(selectedJobId);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activePage, selectedJobId]);

  useEffect(() => {
    const pageCount = Math.max(1, Math.ceil(jobs.length / jobPageSize));
    if (jobPage > pageCount) setJobPage(pageCount);
  }, [jobPage, jobs.length]);

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
    setJobsRefreshedAt(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  }

  async function startFullCollection() {
    const platforms = config.platforms.filter(Boolean);
    if (!platforms.length) {
      showToast("配置页还没有启用平台，请先到采集配置添加平台。");
      return;
    }
    const ok = window.confirm(
      `你将真实启动“完整采集流程”。\n平台：${platforms.map(formatPlatform).join("、")}\n这会调用本机 OpenCLI 和平台登录态。确认继续吗？`
    );
    if (!ok) return;

    const response = await fetch("/api/v1/collection/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: platforms.join(","), stage: "all", dry_run: false })
    });
    if (!response.ok) {
      showToast("完整采集流程提交失败，请到系统诊断查看 OpenCLI 和后台状态。");
      void fetchJobs();
      return;
    }
    const job = await response.json();

    setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
    setJobPage(1);
    showToast(`已提交完整采集流程：${platforms.map(formatPlatform).join("、")}`);
    if (job.id) void fetchJobLog(job.id);
    void fetchJobs();
  }

  async function fetchJobLog(jobId: string) {
    try {
      const response = await fetch(`/api/v1/collection/jobs/${jobId}/log`);
      setJobLog(response.ok ? await response.text() : "");
      setSelectedJobId(jobId);
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
    const payload = await response.json();
    setCandidates((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, ...(payload.candidate || {}), human_status: status } : item
      )
    );
    showToast(status === "approved" ? "已确认候选情报" : "已驳回候选情报");
  }

  async function moveCandidateToTrash(id: string) {
    const response = await fetch("/api/v1/trash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_type: "candidate", ids: [id], reason: "后台人工软删除" })
    });
    if (response.ok) {
      setLocallyDeletedCandidateIds((prev) => Array.from(new Set([...prev, id])));
      showToast("已移入软删除回收站");
    } else {
      showToast("移入回收站失败");
    }
    void refreshAll();
  }

  async function restoreCandidateFromTrash(id: string) {
    const response = await fetch("/api/v1/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id] })
    });
    if (response.ok) {
      setLocallyDeletedCandidateIds((prev) => prev.filter((item) => item !== id));
      setTrash((prev) => prev.filter((item) => item.id !== id));
      showToast("已撤销软删除");
    } else {
      showToast("撤销删除失败");
    }
    void refreshAll();
  }

  async function restoreTrash() {
    const response = await fetch("/api/v1/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: selectedTrashIds })
    });
    showToast(response.ok ? "已恢复所选条目" : "恢复失败");
    if (response.ok) setLocallyDeletedCandidateIds((prev) => prev.filter((id) => !selectedTrashIds.includes(id)));
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
  const jobPageCount = Math.max(1, Math.ceil(jobs.length / jobPageSize));
  const visibleJobs = useMemo(
    () => jobs.slice((jobPage - 1) * jobPageSize, jobPage * jobPageSize),
    [jobPage, jobs]
  );
  const deletedCandidateIds = useMemo(() => {
    const ids = new Set(locallyDeletedCandidateIds);
    trash.forEach((item) => {
      if (item.item_type === "candidate" || item.payload_json?.id) ids.add(String(item.id));
    });
    return ids;
  }, [locallyDeletedCandidateIds, trash]);
  const pendingCandidates = useMemo(
    () => candidates.filter((item) => !deletedCandidateIds.has(String(item.id)) && (item.human_status || "pending") === "pending"),
    [candidates, deletedCandidateIds]
  );
  const approvedCandidates = useMemo(
    () => candidates.filter((item) => !deletedCandidateIds.has(String(item.id)) && item.human_status === "approved"),
    [candidates, deletedCandidateIds]
  );
  const rejectedCandidates = useMemo(
    () => candidates.filter((item) => !deletedCandidateIds.has(String(item.id)) && item.human_status === "rejected"),
    [candidates, deletedCandidateIds]
  );
  const deletedCandidates = useMemo(
    () => candidates.filter((item) => deletedCandidateIds.has(String(item.id))),
    [candidates, deletedCandidateIds]
  );
  const candidateTagCounts = useMemo(() => buildTagCounts(candidates), [candidates]);
  const filteredTitles = useMemo(() => {
    const query = titleSearch.trim().toLowerCase();
    if (!query) return titles;
    return titles.filter((item) => getTitleSearchText(item).includes(query));
  }, [titleSearch, titles]);

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

      <main className="min-w-0 flex-1 overflow-x-clip">
        <header className="sticky top-0 z-20 border-b border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground">V0.2.4 后台控制台</p>
              <h1 className="text-2xl font-black tracking-normal">以太情报后台</h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ThemeSwitch mode={themeMode} onChange={setThemeMode} />
              <Badge tone="success">本机免登录</Badge>
              <Badge tone="warning">自动审议，不自动发布</Badge>
              <Badge tone="info">127.0.0.1</Badge>
            </div>
          </div>
        </header>

        {toast && <div className="mx-4 mt-4 rounded-md border border-border bg-card px-4 py-3 text-sm md:mx-6">{toast}</div>}

        <div className="space-y-6 p-4 md:p-6">
          {activePage === "采集操作台" && (
            <Page title="采集操作台" icon={<Activity className="h-5 w-5" />}>
              <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                <Card>
                  <CardHeader>
                    <CardTitle>启动完整采集流程</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <Field label="目标平台">
                      <div className="flex flex-wrap gap-2">
                        {config.platforms.length ? config.platforms.map((platform) => (
                          <PlatformBadge key={platform} platform={platform} />
                        )) : (
                          <Badge tone="warning">未配置平台</Badge>
                        )}
                      </div>
                    </Field>
                    <button aria-label="启动完整采集流程" onClick={() => void startFullCollection()} className="w-full rounded-md border border-primary bg-primary p-4 text-left text-primary-foreground transition hover:brightness-95">
                      <div className="flex items-center justify-between gap-3">
                        <strong>启动完整采集流程</strong>
                        <Play className="h-4 w-4" />
                      </div>
                      <p className="mt-2 text-xs text-primary-foreground/80">使用采集配置里的平台与参数，按 24 小时采集流程提交任务，后台记录阶段、退出码和日志。</p>
                    </button>
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
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs text-muted-foreground">{jobsRefreshedAt ? `上次刷新 ${jobsRefreshedAt}` : "每 5 秒自动刷新"}</span>
                        <Button variant="secondary" onClick={() => void fetchJobs()}><RefreshCcw className="h-4 w-4" />刷新</Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <DataTable
                      testId="collection-job-table"
                      items={visibleJobs}
                      empty="暂无采集任务。点击“启动完整采集流程”后，这里会显示任务状态、阶段和日志入口。"
                      columns={[
                        ["任务", (job) => <button className="font-mono text-primary hover:underline" onClick={() => void fetchJobLog(job.id)}>{job.id}</button>],
                        ["平台", (job) => <PlatformBadgeGroup platform={job.platform} />],
                        ["阶段", (job) => <StageBadge stage={job.stage} />],
                        ["状态", (job) => <StatusBadge status={job.status} />],
                        ["操作", (job) => ["queued", "running", "cancelling"].includes(String(job.status)) ? (
                          <Button variant="danger" onClick={() => void cancelJob(job.id)}>停止</Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">无需操作</span>
                        )]
                      ]}
                    />
                    {jobs.length > 0 && (
                      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
                        <span className="text-muted-foreground">第 {jobPage} / {jobPageCount} 页，共 {jobs.length} 个任务</span>
                        <div className="flex gap-2">
                          <Button variant="secondary" disabled={jobPage <= 1} onClick={() => setJobPage((page) => Math.max(1, page - 1))}>上一页</Button>
                          <Button variant="secondary" disabled={jobPage >= jobPageCount} onClick={() => setJobPage((page) => Math.min(jobPageCount, page + 1))}>下一页</Button>
                        </div>
                      </div>
                    )}
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
                <CardHeader>
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                    <CardTitle>最新标题池文件{titleMeta.file ? `：${titleMeta.file}` : ""}</CardTitle>
                    <span className="text-sm text-muted-foreground">采集日期：{formatDateTime(titleMeta.collected_at)}</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-4 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <label className="space-y-2">
                      <span className="block text-xs font-semibold text-muted-foreground">检索标题池</span>
                      <div className="flex min-h-10 items-center gap-2 rounded-md bg-muted px-3">
                        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <input
                          aria-label="检索标题池"
                          className="min-h-10 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                          placeholder="输入标题、平台、关键词、摘要、ID 或链接"
                          value={titleSearch}
                          onChange={(event) => setTitleSearch(event.target.value)}
                        />
                      </div>
                    </label>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span>显示 {filteredTitles.length} / {titles.length}</span>
                      {titleSearch && <Button variant="secondary" onClick={() => setTitleSearch("")}>清空</Button>}
                    </div>
                  </div>
                  <DataTable
                    items={filteredTitles}
                    empty={titles.length ? "没有找到匹配的标题池数据" : "暂无标题池数据"}
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
                    empty={`暂无 ASR 结果。${videoMeta.empty_reason || "先在采集操作台运行完整采集流程。"}`}
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
              <div className="space-y-4">
                <CandidateReviewSection
                  title="候选待确认"
                  items={pendingCandidates}
                  empty={candidates.length ? "候选待确认暂无议题。" : "暂无候选情报。先运行采集与审议流程。"}
                  onApprove={postDecision}
                  onReject={postDecision}
                  onTrash={moveCandidateToTrash}
                  onRestore={restoreCandidateFromTrash}
                  tagCounts={candidateTagCounts}
                />
                {candidates.length > 0 && pendingCandidates.length === 0 && (
                  <div className="rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white">当日选题已人工确认完毕</div>
                )}
                <CandidateReviewSection
                  title="已确认"
                  items={approvedCandidates}
                  empty="暂无已确认议题。"
                  onApprove={postDecision}
                  onReject={postDecision}
                  onTrash={moveCandidateToTrash}
                  onRestore={restoreCandidateFromTrash}
                  tagCounts={candidateTagCounts}
                />
                <CandidateReviewSection
                  title="已驳回"
                  items={rejectedCandidates}
                  empty="暂无已驳回议题。"
                  onApprove={postDecision}
                  onReject={postDecision}
                  onTrash={moveCandidateToTrash}
                  onRestore={restoreCandidateFromTrash}
                  tagCounts={candidateTagCounts}
                />
                <CandidateReviewSection
                  title="软删除"
                  items={deletedCandidates}
                  empty="暂无软删除议题。"
                  deleted
                  onApprove={postDecision}
                  onReject={postDecision}
                  onTrash={moveCandidateToTrash}
                  onRestore={restoreCandidateFromTrash}
                  tagCounts={candidateTagCounts}
                />
              </div>
            </Page>
          )}

          {activePage === "交叉验证" && (
            <Page title="交叉验证" icon={<ShieldAlert className="h-5 w-5" />}>
              <RecordCards
                items={crossCheckItems}
                empty="暂无交叉验证数据。候选条目生成 cross_check 后会显示 claim、支持来源、冲突来源和补证建议。"
                render={(item) => <CrossCheckCard item={item} />}
              />
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

function ThemeSwitch({ mode, onChange }: { mode: ThemeMode; onChange: (mode: ThemeMode) => void }) {
  const options: { icon: React.ReactNode; label: string; value: ThemeMode }[] = [
    { icon: <Monitor className="h-3.5 w-3.5" />, label: "系统", value: "system" },
    { icon: <Sun className="h-3.5 w-3.5" />, label: "浅色", value: "light" },
    { icon: <Moon className="h-3.5 w-3.5" />, label: "深色", value: "dark" }
  ];
  return (
    <div className="inline-flex rounded-md bg-muted p-1 shadow-sm">
      {options.map((option) => (
        <button
          key={option.value}
          aria-pressed={mode === option.value}
          className={`inline-flex min-h-8 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition ${
            mode === option.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
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
  if (value === "rejected") {
    return <Badge tone="neutral" className="bg-danger text-white dark:bg-danger dark:text-white">{statusLabels[value]}</Badge>;
  }
  const tone = ["succeeded", "completed", "approved", "ok"].includes(value) ? "success" : ["failed", "rejected", "deleted"].includes(value) ? "danger" : ["running", "pending"].includes(value) ? "info" : "warning";
  return <Badge tone={tone as any}>{statusLabels[value] || value}</Badge>;
}

function StageBadge({ stage }: { stage?: string }) {
  const value = stage || "unknown";
  const tone = value === "all" ? "info" : value === "screen" ? "success" : "neutral";
  return <Badge tone={tone as any}>{stageLabels[value] || value}</Badge>;
}

function PlatformBadgeGroup({ platform }: { platform?: string }) {
  const platforms = String(platform || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (!platforms.length) return <span>-</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {platforms.map((item) => <PlatformBadge key={item} platform={item} />)}
    </div>
  );
}

function PlatformBadge({ platform }: { platform: string }) {
  return (
    <Badge tone="info" icon={<PlatformIcon platform={platform} />}>
      {formatPlatform(platform)}
    </Badge>
  );
}

function PlatformIcon({ platform }: { platform: string }) {
  if (platform === "xiaohongshu") {
    return <span className="grid h-[18px] w-[18px] place-items-center rounded-[5px] bg-red-600 text-[9px] font-black leading-none text-white">小</span>;
  }
  if (platform === "douyin") {
    return <span className="grid h-[18px] w-[18px] place-items-center rounded-[5px] bg-slate-950 text-[13px] font-black leading-none text-cyan-300">♪</span>;
  }
  return <Globe2 className="h-3.5 w-3.5" />;
}

function CrossCheckCard({ item }: { item: AnyRecord }) {
  const crossCheck = item.cross_check || {};
  const supportSources = normalizeSourceList(crossCheck.supporting_sources ?? item.support_sources);
  const conflictSources = normalizeSourceList(crossCheck.conflicting_sources ?? item.conflict_sources);
  const needsMoreSources = Boolean(crossCheck.needs_more_sources ?? item.needs_more_sources);
  const reasoning = formatCrossCheckReason(crossCheck.reasoning || item.cross_check_reasoning);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold tracking-normal">{item.claim || getTitle(item)}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{getSummary(item)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CrossCheckStatusBadge status={crossCheck.status || item.cross_check_status} />
          <Badge tone={needsMoreSources ? "warning" : "success"}>{needsMoreSources ? "需要补证" : "补证充足"}</Badge>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <SourcePanel title="支持来源" sources={supportSources} empty="暂无支持来源" />
        <SourcePanel title="冲突来源" sources={conflictSources} empty="暂无冲突来源" />
      </div>

      <div className="rounded-md bg-background p-4 shadow-sm">
        <Badge tone="neutral">智脑核验判断</Badge>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{reasoning}</p>
      </div>
    </div>
  );
}

function CrossCheckStatusBadge({ status }: { status?: string }) {
  const value = String(status || "unverified").toLowerCase();
  const label =
    value === "verified" ? "已验证" :
    value === "partially_verified" || value === "partial" ? "部分验证" :
    value === "conflict" || value === "conflicting" ? "存在冲突" :
    value === "unverified" ? "未验证" :
    value;
  const tone =
    label === "已验证" ? "success" :
    label === "部分验证" ? "info" :
    label === "存在冲突" || label === "未验证" ? "warning" :
    "neutral";
  return <Badge tone={tone as any}>{label}</Badge>;
}

function SourcePanel({ title, sources, empty }: { title: string; sources: string[]; empty: string }) {
  return (
    <div className="rounded-md bg-background p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <Badge tone="neutral">{title}</Badge>
        <span className="text-xs text-muted-foreground">{sources.length} 条</span>
      </div>
      {sources.length ? (
        <div className="grid gap-2">
          {sources.map((source, index) => (
            <div key={`${source}-${index}`} className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
              {formatSourceLabel(source)}
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function normalizeSourceList(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return [String(value).trim()].filter(Boolean);
}

function formatSourceLabel(source: string): string {
  if (!source || source === "redacted") return "来源缺失";
  return source;
}

function formatCrossCheckReason(reason?: string): string {
  if (!reason) return "暂无明确核验判断。";
  const normalized = reason.trim();
  if (normalized.includes("Multiple posts from Xiaohongshu about the same hotel")) {
    return "小红书上多条同类内容相互印证，说明该议题有热度；但目前缺少独立平台或官方来源，所以真实性和商业推广属性仍需要继续确认。";
  }
  if (normalized.includes("Single detailed post")) {
    return "目前主要来自单条详细内容，虽然旅行论坛或社媒上可能有相似讨论，但还需要直接补充来源来确认。";
  }
  if (normalized.includes("Three separate Xiaohongshu posts corroborate")) {
    return "三条不同小红书内容指向同一事件，社媒层面的可信度较高；如果要作为正式判断，仍建议补充官方公告或现场来源。";
  }
  if (/^[\x00-\x7F\s.,;:'"!?()/-]+$/.test(normalized)) {
    return `该核验判断来自英文审议结果，后续需要智脑统一翻译。原始判断：${normalized}`;
  }
  return normalized;
}

function CandidateReviewSection({
  title,
  items,
  empty,
  deleted = false,
  onApprove,
  onReject,
  onTrash,
  onRestore,
  tagCounts,
}: {
  title: string;
  items: AnyRecord[];
  empty: string;
  deleted?: boolean;
  onApprove: (id: string, status: "approved" | "rejected") => Promise<void>;
  onReject: (id: string, status: "approved" | "rejected") => Promise<void>;
  onTrash: (id: string) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
  tagCounts: Record<string, number>;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{title}</CardTitle>
          <Badge tone={items.length ? "info" : "neutral"}>{items.length}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {items.length ? (
          <div className="grid gap-3">
            {items.map((item) => (
              <CandidateReviewCard
                key={item.id}
                item={item}
                deleted={deleted}
                onApprove={onApprove}
                onReject={onReject}
                onTrash={onTrash}
                onRestore={onRestore}
                tagCounts={tagCounts}
              />
            ))}
          </div>
        ) : (
          <EmptyState text={empty} />
        )}
      </CardContent>
    </Card>
  );
}

function CandidateReviewCard({
  item,
  deleted,
  onApprove,
  onReject,
  onTrash,
  onRestore,
  tagCounts,
}: {
  item: AnyRecord;
  deleted: boolean;
  onApprove: (id: string, status: "approved" | "rejected") => Promise<void>;
  onReject: (id: string, status: "approved" | "rejected") => Promise<void>;
  onTrash: (id: string) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
  tagCounts: Record<string, number>;
}) {
  const originalTitle = getOriginalTitle(item);
  const originalSummary = getOriginalSummary(item);
  const translatedTitle = getReverseTranslatedTitle(item, originalTitle);
  const translatedSummary = getReverseTranslatedSummary(item, originalTitle);
  return (
    <div className="rounded-md bg-muted/45 p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_120px_112px_112px_220px] xl:items-center">
        <div className="min-w-0 space-y-3">
          <div data-testid="candidate-original-panel" className="rounded-md bg-slate-950 p-4 text-white shadow-sm dark:bg-slate-950">
            <Badge tone="neutral">原文</Badge>
            <h3 className="mt-3 text-base font-semibold tracking-normal text-white">{originalTitle}</h3>
            <p className="mt-2 text-sm text-slate-300">{originalSummary}</p>
          </div>
          <div className="rounded-md bg-background p-3">
            <Badge tone="neutral">翻译</Badge>
            <p className="mt-2 text-sm font-medium">{translatedTitle}</p>
            <p className="mt-1 text-xs text-muted-foreground">{translatedSummary}</p>
          </div>
          <CandidateTagHeat tags={getCandidateTags(item)} tagCounts={tagCounts} />
        </div>
        <div className="flex items-center justify-center"><PlatformBadgeGroup platform={item.platform} /></div>
        <div className="flex items-center justify-center"><StatusBadge status={deleted ? "deleted" : item.human_status || item.status || "pending"} /></div>
        <div className="flex items-center justify-center"><ScoreBadge score={item.score ?? item.weight} /></div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {!deleted && <Button onClick={() => void onApprove(item.id, "approved")}><Check className="h-4 w-4" />确认</Button>}
          {!deleted && <Button variant="danger" onClick={() => void onReject(item.id, "rejected")}><X className="h-4 w-4" />驳回</Button>}
          {deleted ? (
            <Button variant="secondary" onClick={() => void onRestore(item.id)}>撤销删除</Button>
          ) : (
            <Button variant="secondary" onClick={() => void onTrash(item.id)}>软删除</Button>
          )}
        </div>
      </div>
      <GeoRiskNotice item={item} />
    </div>
  );
}

function getOriginalTitle(item: AnyRecord): string {
  return item.title_original || item.original_title || item.raw_title || item.title || item.display?.title || getTitle(item);
}

function getOriginalSummary(item: AnyRecord): string {
  return item.summary_original || item.original_summary || item.raw_summary || item.summary || item.text || item.display?.summary || "暂无原文摘要";
}

function getReverseTranslatedTitle(item: AnyRecord, originalTitle: string): string {
  if (hasChineseText(originalTitle)) {
    return item.display?.title_en || item.title_en || item.en_title || item.translated_title || item.display?.title || "暂无英文翻译";
  }
  return item.display?.title_zh || item.title_zh || item.zh_title || item.translated_title || "暂无中文翻译";
}

function getReverseTranslatedSummary(item: AnyRecord, originalTitle: string): string {
  if (hasChineseText(originalTitle)) {
    return item.display?.summary_en || item.summary_en || item.en_summary || item.translated_summary || item.display?.summary || "暂无英文翻译摘要";
  }
  return item.display?.summary_zh || item.summary_zh || item.zh_summary || item.translated_summary || "暂无中文翻译摘要";
}

function hasChineseText(value: string): boolean {
  return /[\u4e00-\u9fff]/.test(value);
}

function CandidateTagHeat({ tags, tagCounts }: { tags: string[]; tagCounts: Record<string, number> }) {
  if (!tags.length) return null;
  return (
    <div className="rounded-md bg-background p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <Badge tone="neutral">标签热度</Badge>
        <span className="text-xs text-muted-foreground">按当日候选重复度计算</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className={`inline-flex min-h-8 items-center rounded-md px-3 text-xs font-bold shadow-sm ${getTagHeatClass(tag, tagCounts)}`}>
            {tag} ×{tagCounts[tag] || 1}
          </span>
        ))}
      </div>
    </div>
  );
}

function buildTagCounts(items: AnyRecord[]): Record<string, number> {
  return items.reduce<Record<string, number>>((counts, item) => {
    getCandidateTags(item).forEach((tag) => {
      counts[tag] = (counts[tag] || 0) + 1;
    });
    return counts;
  }, {});
}

function getCandidateTags(item: AnyRecord): string[] {
  const raw = [
    item.tags,
    item.advisor_tags,
    item.topic_tags,
    item.signals,
    item.category,
  ].flatMap((value) => Array.isArray(value) ? value : value ? [value] : []);
  return Array.from(new Set(raw.map((tag) => String(tag).trim()).filter(Boolean))).slice(0, 8);
}

function getTagHeatClass(tag: string, tagCounts: Record<string, number>): string {
  const count = tagCounts[tag] || 1;
  const values = Object.values(tagCounts).filter((value) => value > 0);
  const min = Math.min(...values, count);
  const max = Math.max(...values, count);
  if (max === min) {
    return max > 1 ? "bg-red-600 text-white" : "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100";
  }
  const heat = (count - min) / (max - min);
  if (heat >= 0.8) return "bg-red-600 text-white";
  if (heat >= 0.6) return "bg-orange-600 text-white";
  if (heat >= 0.4) return "bg-amber-500 text-white";
  if (heat >= 0.2) return "bg-lime-500 text-white";
  return "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100";
}

function ScoreBadge({ score }: { score?: number | string }) {
  const parsed = Number(score);
  if (Number.isNaN(parsed)) return <Badge tone="neutral">-</Badge>;
  const value = Math.max(0, Math.min(100, Math.round(parsed)));
  const color =
    value >= 81 ? "bg-emerald-600 text-white" :
    value >= 61 ? "bg-lime-600 text-white" :
    value >= 41 ? "bg-amber-500 text-white" :
    value >= 21 ? "bg-orange-600 text-white" :
    "bg-red-600 text-white";
  return <span className={`grid h-12 min-w-12 place-items-center rounded-md px-3 text-lg font-black ${color}`}>{value}</span>;
}

function GeoRiskNotice({ item }: { item: AnyRecord }) {
  const risk = item.geo_risk || {};
  const probability = normalizeProbability(risk.probability ?? item.geo_risk_score ?? item.geo_risk_probability) ?? 0;
  const probabilityText = `${Math.round(probability * 100)}%`;
  const riskClass = probability >= 0.7 ? "text-red-600" : probability >= 0.5 ? "text-orange-600" : probability >= 0.3 ? "text-amber-600" : "text-emerald-600";
  const reasons = Array.isArray(risk.reasons) ? risk.reasons.join("；") : risk.reasons;
  return (
    <div className="mt-4 rounded-md bg-white p-4 text-sm shadow-sm dark:bg-slate-950">
      <div className="flex flex-wrap items-center gap-2">
        <Radar className={`h-4 w-4 ${riskClass}`} />
        <strong>生成式搜索风险</strong>
        <span className={`font-black ${riskClass}`}>{probabilityText}</span>
        <Badge tone={probability >= 0.6 ? "danger" : "neutral"}>{formatGeoRiskLevel(risk.level, probability)}</Badge>
      </div>
      <p className="mt-2 text-muted-foreground">智脑分析原因：{reasons || "暂无明确原因。"}</p>
    </div>
  );
}

function normalizeProbability(value: unknown): number | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized.endsWith("%")) return Math.max(0, Math.min(1, Number(normalized.slice(0, -1)) / 100));
    if (normalized === "high") return 0.8;
    if (normalized === "medium") return 0.5;
    if (normalized === "low") return 0.2;
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return null;
  return Math.max(0, Math.min(1, numeric > 1 ? numeric / 100 : numeric));
}

function formatGeoRiskLevel(level: unknown, probability: number | null): string {
  const normalized = String(level || "").toLowerCase();
  if (normalized === "high") return "高风险";
  if (normalized === "medium") return "中风险";
  if (normalized === "low") return "低风险";
  if (normalized === "very_low" || normalized === "minimal") return "极小风险";
  if (probability === null) return "未评级";
  if (probability >= 0.7) return "高风险";
  if (probability >= 0.4) return "中风险";
  if (probability <= 0.05) return "极小风险";
  return "低风险";
}

function DataTable({ items, empty, columns, testId }: { items: AnyRecord[]; empty: string; columns: [string, (item: AnyRecord) => React.ReactNode][]; testId?: string }) {
  if (!items.length) return <EmptyState text={empty} />;
  return (
    <div data-testid={testId} className="overflow-x-auto rounded-md border border-border">
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
