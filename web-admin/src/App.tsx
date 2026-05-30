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
  Info,
  Languages,
  ListFilter,
  Monitor,
  Moon,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Radar,
  RefreshCcw,
  Search,
  Settings,
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
type LanguageMode = "zh" | "en";
type CollectionRunMode = "manual" | "auto";
type CollectionModeId = "shellCLI" | "agentCLI";
type CollectionAction = "manual_web" | "collect" | "clean" | "package" | "auto_pipeline";
type PageId =
  | "collection-console"
  | "collection-config"
  | "title-pool"
  | "video-processing"
  | "candidate-review"
  | "cross-check"
  | "official-sources"
  | "daily-bundles"
  | "retention"
  | "cloud-logs"
  | "agent-apis"
  | "trash"
  | "system-diagnosis"
  | "release"
  | "global-settings";

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

const pageMeta: Record<PageId, { icon: typeof Activity; zh: string; en: string }> = {
  "collection-console": { icon: Activity, zh: "采集操作台", en: "Collection Console" },
  "collection-config": { icon: SlidersHorizontal, zh: "采集配置", en: "Collection Config" },
  "title-pool": { icon: ListFilter, zh: "标题池", en: "Title Pool" },
  "video-processing": { icon: Video, zh: "语音转文字深处理", en: "ASR Processing" },
  "candidate-review": { icon: ClipboardCheck, zh: "候选审阅", en: "Candidate Review" },
  "cross-check": { icon: ShieldAlert, zh: "交叉验证", en: "Cross Check" },
  "official-sources": { icon: Globe2, zh: "官方信源", en: "Official Sources" },
  "daily-bundles": { icon: Boxes, zh: "每日资料包", en: "Daily Bundles" },
  retention: { icon: Database, zh: "证据保留", en: "Evidence Retention" },
  "cloud-logs": { icon: Cloud, zh: "云日志边界", en: "Cloud Log Boundary" },
  "agent-apis": { icon: FileJson, zh: "后续智能体接口", en: "Agent APIs" },
  trash: { icon: Trash2, zh: "软删除回收站", en: "Soft Delete Trash" },
  "system-diagnosis": { icon: Gauge, zh: "系统诊断", en: "System Diagnosis" },
  release: { icon: ArchiveRestore, zh: "版本发布", en: "Release" },
  "global-settings": { icon: Settings, zh: "全局设置", en: "Global Settings" }
};

const navSections: { id: string; zh: string; en: string; pages: PageId[] }[] = [
  { id: "collection", zh: "采集控制", en: "Collection", pages: ["collection-console", "collection-config"] },
  { id: "intelligence", zh: "情报处理", en: "Intelligence", pages: ["title-pool", "video-processing", "candidate-review"] },
  { id: "verification", zh: "核验信源", en: "Verification", pages: ["cross-check", "official-sources"] },
  { id: "output", zh: "输出接口", en: "Output", pages: ["daily-bundles", "retention", "cloud-logs", "agent-apis"] },
  { id: "governance", zh: "数据治理", en: "Governance", pages: ["trash"] }
];

const utilityPages: PageId[] = ["system-diagnosis", "release", "global-settings"];

const stageLabels: Record<string, string> = {
  titles: "采集标题池",
  screen: "机会风险初筛",
  videos: "视频语音处理",
  all: "采集执行",
  clean: "清理数据",
  package: "打包资料包"
};

const collectionActionLabels: Record<CollectionAction, string> = {
  manual_web: "网页手动启动",
  collect: "启动自动化任务采集",
  clean: "清理数据",
  package: "生成当日资料包",
  auto_pipeline: "自动执行三步流程"
};

const platformLabels: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  wechat_channels: "视频号"
};

const jobPageSize = 8;
const collectionModes: { id: CollectionModeId; title: string; subtitle: string; path: string; tone: "blue" | "emerald" }[] = [
  {
    id: "shellCLI",
    title: "采集模式一（脚本主导）",
    subtitle: "固定脚本和 OpenCLI 执行低成本日常采集",
    path: "/Users/gugu/Documents/Agent/AetherFlux_yitaitongliang/aetherflux_shellCLI",
    tone: "blue"
  },
  {
    id: "agentCLI",
    title: "采集模式二（Agent主导）",
    subtitle: "Agent 负责复杂页面、异常处理和高价值线索深挖",
    path: "/Users/gugu/Documents/Agent/AetherFlux_yitaitongliang/aetherflux_agentCLI",
    tone: "emerald"
  }
];
const themeStorageKey = "aetherflux-admin-theme";
const languageStorageKey = "aetherflux-admin-language";
const sidebarStorageKey = "aetherflux-admin-sidebar-collapsed";
const primaryColorStorageKey = "aetherflux-admin-primary-color";
const analysisColorStorageKey = "aetherflux-admin-analysis-color";

const primaryColorOptions = [
  { name: "紫色", value: "263 68% 58%", className: "bg-violet-600" },
  { name: "蓝色", value: "221 83% 53%", className: "bg-blue-600" },
  { name: "绿色", value: "150 70% 38%", className: "bg-emerald-600" },
  { name: "橙色", value: "24 95% 53%", className: "bg-orange-600" },
  { name: "石板灰", value: "215 20% 48%", className: "bg-slate-500" }
];

const analysisColorOptions = [
  { name: "薄荷绿", value: "158 72% 52%", className: "bg-emerald-400" },
  { name: "天空蓝", value: "199 89% 58%", className: "bg-sky-400" },
  { name: "琥珀黄", value: "43 96% 56%", className: "bg-amber-400" },
  { name: "珊瑚红", value: "350 89% 68%", className: "bg-rose-400" },
  { name: "紫色", value: "258 85% 72%", className: "bg-violet-400" },
  { name: "暖橙", value: "27 96% 61%", className: "bg-orange-400" }
];

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

function getInitialLanguageMode(): LanguageMode {
  if (typeof window === "undefined") return "zh";
  return window.localStorage.getItem(languageStorageKey) === "en" ? "en" : "zh";
}

function getInitialSidebarCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(sidebarStorageKey) === "true";
}

function getInitialColor(storageKey: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return window.localStorage.getItem(storageKey) || fallback;
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

function pageLabel(page: PageId, language: LanguageMode): string {
  return pageMeta[page][language];
}

function formatCollectionMode(mode?: string): string {
  if (mode === "shellCLI") return "采集模式一（脚本主导）";
  if (mode === "agentCLI") return "采集模式二（Agent主导）";
  return "旧采集流程";
}

export default function App() {
  const [activePage, setActivePage] = useState<PageId>("collection-console");
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
  const [languageMode, setLanguageMode] = useState<LanguageMode>(getInitialLanguageMode);
  const [collectionRunMode, setCollectionRunMode] = useState<CollectionRunMode>("manual");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(getInitialSidebarCollapsed);
  const [primaryColor, setPrimaryColor] = useState(() => getInitialColor(primaryColorStorageKey, primaryColorOptions[0].value));
  const [analysisColor, setAnalysisColor] = useState(() => getInitialColor(analysisColorStorageKey, analysisColorOptions[0].value));
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
      root.style.setProperty("--primary", primaryColor);
      root.style.setProperty("--analysis", analysisColor);
      window.localStorage.setItem(themeStorageKey, themeMode);
      window.localStorage.setItem(primaryColorStorageKey, primaryColor);
      window.localStorage.setItem(analysisColorStorageKey, analysisColor);
    };
    applyTheme();
    if (themeMode !== "system" || !media) return;
    media.addEventListener?.("change", applyTheme);
    return () => media.removeEventListener?.("change", applyTheme);
  }, [analysisColor, primaryColor, themeMode]);

  useEffect(() => {
    window.localStorage.setItem(languageStorageKey, languageMode);
  }, [languageMode]);

  useEffect(() => {
    window.localStorage.setItem(sidebarStorageKey, String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    setEditConfig({ ...defaultConfig, ...config });
  }, [config]);

  useEffect(() => {
    if (activePage !== "collection-console") return;
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

  async function startCollectionJob(mode: CollectionModeId, action: CollectionAction) {
    const platforms = config.platforms.filter(Boolean);
    if (!platforms.length) {
      showToast("配置页还没有启用平台，请先到采集配置添加平台。");
      return;
    }
    const queries = (config.manual_queries || []).filter(Boolean);
    if (!queries.length) {
      showToast("配置页还没有配置采集关键词，请先前往配置。");
      return;
    }
    const actionName = collectionActionLabels[action];
    const ok = window.confirm(`确认执行 ${formatCollectionMode(mode)} 的“${actionName}”吗？\n平台：${platforms.map(formatPlatform).join("、")}\n后台会保留任务包、退出码和日志。`);
    if (!ok) return;

    const response = await fetch("/api/v1/collection/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: platforms.join(","),
        stage: action === "package" ? "package" : action === "clean" ? "clean" : "all",
        mode,
        action,
        run_mode: collectionRunMode,
        dry_run: false,
        queries: config.manual_queries.join(",")
      })
    });
    if (!response.ok) {
      showToast(`${actionName} 提交失败，请到系统诊断查看后台状态。`);
      void fetchJobs();
      return;
    }
    const job = await response.json();

    setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
    setJobPage(1);
    showToast(`已提交${actionName}：${formatCollectionMode(mode)}`);
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
    <div className="flex min-h-dvh min-w-[320px] bg-background text-foreground">
      <aside
        data-testid="admin-sidebar"
        className={`sticky top-0 flex h-dvh shrink-0 flex-col border-r border-border bg-card px-3 py-4 transition-[width] duration-200 ${
          sidebarCollapsed ? "w-[88px]" : "w-[292px]"
        }`}
      >
        <div className={`mb-4 flex items-center gap-3 ${sidebarCollapsed ? "justify-center" : ""}`}>
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-primary text-sm font-black text-primary-foreground">AF</div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">{languageMode === "zh" ? "以太通量后台" : "AetherFlux Admin"}</p>
              <p className="truncate text-xs text-muted-foreground">AetherFlux · {summary.version || "V0.2.4"}</p>
            </div>
          )}
        </div>
        <nav className="min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="grid gap-4">
            {navSections.map((section) => (
              <div key={section.id} className="grid gap-1">
                {!sidebarCollapsed && (
                  <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    {section[languageMode]}
                  </p>
                )}
                {section.pages.map((page) => (
                  <SidebarButton
                    key={page}
                    active={activePage === page}
                    collapsed={sidebarCollapsed}
                    icon={pageMeta[page].icon}
                    label={pageLabel(page, languageMode)}
                    onClick={() => setActivePage(page)}
                  />
                ))}
              </div>
            ))}
          </div>
        </nav>
        <nav data-testid="sidebar-utility-nav" className="mt-4 grid gap-1 border-t border-border pt-3">
          {utilityPages.map((page) => (
            <SidebarButton
              key={page}
              active={activePage === page}
              collapsed={sidebarCollapsed}
              icon={pageMeta[page].icon}
              label={pageLabel(page, languageMode)}
              onClick={() => setActivePage(page)}
            />
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-x-clip">
        <header className="sticky top-0 z-20 border-b border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <button
                aria-label={sidebarCollapsed ? "展开菜单" : "折叠菜单"}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
                onClick={() => setSidebarCollapsed((value) => !value)}
                type="button"
              >
                {sidebarCollapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
              </button>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-muted-foreground">AetherFlux Intelligence Console</p>
                <h1 className="truncate text-2xl font-black tracking-normal">以太情报后台</h1>
              </div>
            </div>
          </div>
        </header>

        {toast && <div className="mx-4 mt-4 rounded-md border border-border bg-card px-4 py-3 text-sm md:mx-6">{toast}</div>}

        <div className="space-y-6 p-4 md:p-6">
          {activePage === "collection-console" && (
            <Page title="采集操作台" icon={<Activity className="h-5 w-5" />}>
              <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <CardTitle>采集流程控制</CardTitle>
                      <div className="inline-flex rounded-full bg-muted p-1" aria-label="采集执行模式">
                        {(["manual", "auto"] as CollectionRunMode[]).map((mode) => (
                          <button
                            key={mode}
                            aria-pressed={collectionRunMode === mode}
                            className={`rounded-full px-4 py-2 text-sm font-bold transition ${collectionRunMode === mode ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                            onClick={() => setCollectionRunMode(mode)}
                            type="button"
                          >
                            {mode === "manual" ? "手动" : "自动"}
                          </button>
                        ))}
                      </div>
                    </div>
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
                    <div className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
                      {collectionRunMode === "manual"
                        ? "手动模式：你在控制台按顺序启动采集、清理、打包三个步骤。两个采集模式可以并行运行。"
                        : "自动模式：点击模式内自动化按钮后，后台按采集、清理、打包的三步结构记录任务和日志。两个采集模式可以并行运行。"}
                    </div>
                    <div className="grid gap-4 2xl:grid-cols-2">
                      {collectionModes.map((mode) => (
                        <CollectionModePanel
                          key={mode.id}
                          mode={mode}
                          jobs={jobs}
                          runMode={collectionRunMode}
                          onStart={(action) => void startCollectionJob(mode.id, action)}
                          onStop={(jobId) => void cancelJob(jobId)}
                        />
                      ))}
                    </div>
                    <div className="grid gap-4 lg:grid-cols-2">
                      <WorkflowStepCard
                        title="第二步：清理数据"
                        description="只做安全扫描、整理和进度记录；不执行物理删除。"
                        jobs={jobs}
                        action="clean"
                        onStart={(mode) => void startCollectionJob(mode, "clean")}
                      />
                      <WorkflowStepCard
                        title="第三步：生成当日资料包"
                        description="生成给第二部分智脑使用的当日资料包，并写入上传/交接日志。"
                        jobs={jobs}
                        action="package"
                        onStart={(mode) => void startCollectionJob(mode, "package")}
                      />
                      </div>
                    <CollectionProgressPanel jobs={jobs} />
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
                      empty="暂无采集任务。启动任一采集模式后，这里会显示任务状态、阶段和日志入口。"
                      columns={[
                        ["任务", (job) => <button className="font-mono text-primary hover:underline" onClick={() => void fetchJobLog(job.id)}>{job.id}</button>],
                        ["模式", (job) => <Badge tone={job.mode === "agentCLI" ? "success" : "info"}>{formatCollectionMode(job.mode)}</Badge>],
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
                <CollectionStatCard label="候选情报" value={counts.candidates || 0} tone="blue" />
                <CollectionStatCard label="已确认" value={counts.approved || 0} tone="emerald" />
                <CollectionStatCard label="风险预警" value={counts.risks || 0} tone="rose" />
                <CollectionStatCard label="生成式搜索高疑似" value={counts.geo_high || 0} tone="amber" />
              </div>
            </Page>
          )}

          {activePage === "collection-config" && (
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

          {activePage === "title-pool" && (
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

          {activePage === "video-processing" && (
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

          {activePage === "candidate-review" && (
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

          {activePage === "cross-check" && (
            <Page title="交叉验证" icon={<ShieldAlert className="h-5 w-5" />}>
              <RecordCards
                items={crossCheckItems}
                empty="暂无交叉验证数据。候选条目生成 cross_check 后会显示 claim、支持来源、冲突来源和补证建议。"
                render={(item) => <CrossCheckCard item={item} />}
              />
            </Page>
          )}

          {activePage === "official-sources" && (
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

          {activePage === "daily-bundles" && <SimpleTablePage title="每日资料包" icon={<Boxes className="h-5 w-5" />} items={dailyBundles} empty="暂无每日资料包记录。" />}

          {activePage === "retention" && (
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

          {activePage === "cloud-logs" && <SimpleTablePage title="云日志边界" icon={<Cloud className="h-5 w-5" />} items={cloudLogs} empty="暂无 Supabase 轻量日志同步记录；不会展示 service key、cookie 或 token。" />}

          {activePage === "system-diagnosis" && (
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

          {activePage === "agent-apis" && <SimpleTablePage title="后续智能体接口" icon={<Bot className="h-5 w-5" />} items={agentApis} empty="暂无接口索引。" />}

          {activePage === "trash" && (
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

          {activePage === "release" && (
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

          {activePage === "global-settings" && (
            <GlobalSettingsPage
              analysisColor={analysisColor}
              languageMode={languageMode}
              onAnalysisColorChange={setAnalysisColor}
              onLanguageChange={setLanguageMode}
              onPrimaryColorChange={setPrimaryColor}
              onThemeChange={setThemeMode}
              primaryColor={primaryColor}
              releaseStatus={releaseStatus}
              themeMode={themeMode}
            />
          )}
        </div>
      </main>
    </div>
  );
}

function SidebarButton({
  active,
  collapsed,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  collapsed: boolean;
  icon: typeof Activity;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      title={collapsed ? label : undefined}
      onClick={onClick}
      className={`flex min-h-11 items-center gap-3 rounded-md text-left text-sm font-semibold transition ${
        collapsed ? "justify-center px-0" : "px-3"
      } ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
      type="button"
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}

function CollectionModePanel({
  mode,
  jobs,
  runMode,
  onStart,
  onStop
}: {
  mode: (typeof collectionModes)[number];
  jobs: AnyRecord[];
  runMode: CollectionRunMode;
  onStart: (action: CollectionAction) => void;
  onStop: (jobId: string) => void;
}) {
  const activeJob = findModeJob(jobs, mode.id, ["collect", "auto_pipeline"]);
  const isRunning = activeJob && ["queued", "running", "cancelling"].includes(String(activeJob.status));
  const action = runMode === "auto" ? "auto_pipeline" : "collect";
  return (
    <section className="rounded-lg bg-card p-4 shadow-sm ring-1 ring-border/80">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-base font-black">{mode.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{mode.subtitle}</p>
        </div>
        <Badge tone={isRunning ? "info" : "neutral"}>{isRunning ? "运行中" : "待启动"}</Badge>
      </div>
      <p className="mt-3 break-all rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">{mode.path}</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <Button variant="secondary" onClick={() => onStart("manual_web")}><Globe2 className="h-4 w-4" />网页手动启动</Button>
        <Button onClick={() => onStart(action)}><Play className="h-4 w-4" />{runMode === "auto" ? "启动自动三步" : "启动自动化任务"}</Button>
        <Button variant="danger" disabled={!activeJob?.id || !isRunning} onClick={() => activeJob?.id && onStop(String(activeJob.id))}>停止采集</Button>
      </div>
      <JobRuntimeStats job={activeJob} emptyName={`${mode.title} 当前无运行任务包`} />
    </section>
  );
}

function WorkflowStepCard({
  title,
  description,
  jobs,
  action,
  onStart
}: {
  title: string;
  description: string;
  jobs: AnyRecord[];
  action: "clean" | "package";
  onStart: (mode: CollectionModeId) => void;
}) {
  const latestJob = jobs.find((job) => job.action === action);
  const percent = latestJob ? getStepPercent(latestJob) : 0;
  return (
    <section className="rounded-lg bg-card p-4 shadow-sm ring-1 ring-border/80">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-black">{title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        </div>
        <Badge tone={latestJob ? (["failed", "cancelled"].includes(String(latestJob.status)) ? "danger" : "success") : "neutral"}>{latestJob ? statusLabels[String(latestJob.status)] || latestJob.status : "未开始"}</Badge>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">当前进度：{percent}%</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <Button variant="secondary" onClick={() => onStart("shellCLI")}>{action === "clean" ? "清理模式一" : "打包模式一"}</Button>
        <Button variant="secondary" onClick={() => onStart("agentCLI")}>{action === "clean" ? "清理模式二" : "打包模式二"}</Button>
      </div>
      <JobRuntimeStats job={latestJob} emptyName="暂无任务包" compact />
    </section>
  );
}

function JobRuntimeStats({ job, emptyName, compact = false }: { job?: AnyRecord; emptyName: string; compact?: boolean }) {
  const stats = getJobStats(job);
  return (
    <div className={`mt-4 grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-4"}`}>
      <MiniStat label="当前任务包" value={stats.name || emptyName} />
      <MiniStat label="已采集" value={stats.items} />
      <MiniStat label="占用磁盘" value={stats.disk} />
      <MiniStat label="已执行" value={stats.duration} />
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0 rounded-md bg-muted/50 px-3 py-2">
      <p className="text-[11px] font-bold text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-black">{value}</p>
    </div>
  );
}

function findModeJob(jobs: AnyRecord[], mode: CollectionModeId, actions: CollectionAction[]) {
  return jobs.find((job) => job.mode === mode && actions.includes(String(job.action) as CollectionAction));
}

function getStepPercent(job: AnyRecord): number {
  if (["succeeded", "completed"].includes(String(job.status))) return 100;
  if (["failed", "cancelled"].includes(String(job.status))) return 100;
  if (String(job.status) === "running") return 55;
  if (String(job.status) === "queued") return 12;
  return 0;
}

function getJobStats(job?: AnyRecord) {
  if (!job) return { name: "", items: 0, disk: "0 KB", duration: "0 分钟" };
  const name = job.package_name || job.bundle_name || job.id || "";
  const items = job.items_collected ?? job.item_count ?? job.collected_count ?? 0;
  const diskBytes = Number(job.disk_bytes ?? job.log_size_bytes ?? job.size_bytes ?? 0);
  return {
    name,
    items,
    disk: formatBytes(diskBytes),
    duration: formatDuration(job.started_at, job.ended_at)
  };
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDuration(start?: string, end?: string): string {
  if (!start) return "0 分钟";
  const startMs = Date.parse(start);
  const endMs = end ? Date.parse(end) : Date.now();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) return "0 分钟";
  const seconds = Math.max(0, Math.floor((endMs - startMs) / 1000));
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (minutes < 60) return `${minutes} 分 ${remain} 秒`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
}

function CollectionProgressPanel({ jobs }: { jobs: AnyRecord[] }) {
  const progress = getCollectionProgress(jobs);
  return (
    <div className="rounded-md bg-slate-950 p-4 text-slate-100 shadow-sm dark:bg-black/35">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">整体采集进度</p>
          <p className="mt-1 text-xs text-slate-400">{progress.jobLabel}</p>
        </div>
        <span className={`text-lg font-black ${progress.percentClass}`}>{progress.percent}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-800">
        <div
          data-testid="collection-progress-fill"
          className={`h-full rounded-full bg-gradient-to-r ${progress.barClass} transition-[width] duration-700 ease-out ${progress.animated ? "animate-pulse" : ""}`}
          style={{ width: `${progress.percent}%` }}
        />
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm text-slate-300">
        <span className={`h-2.5 w-2.5 rounded-full ${progress.dotClass}`} />
        <span>{progress.step}</span>
      </div>
    </div>
  );
}

function getCollectionProgress(jobs: AnyRecord[]) {
  const job = jobs.find((item) => ["queued", "running", "cancelling"].includes(String(item.status))) || jobs[0];
  if (!job) {
    return {
      animated: false,
      barClass: "from-slate-500 to-slate-400",
      dotClass: "bg-slate-500",
      jobLabel: "暂无运行中的采集任务",
      percent: 0,
      percentClass: "text-slate-400",
      step: "等待启动采集任务",
    };
  }

  const explicitPercent = Number(job.progress_percent ?? job.progress);
  const percent = Number.isFinite(explicitPercent)
    ? Math.max(0, Math.min(100, Math.round(explicitPercent)))
    : inferCollectionPercent(job);
  const step = String(job.current_step || job.step_label || inferCollectionStep(job));
  const color = getProgressColor(percent, String(job.status));
  return {
    ...color,
    animated: ["queued", "running", "cancelling"].includes(String(job.status)) && percent < 100,
    jobLabel: job.id ? `当前任务：${job.id}` : "当前任务：未记录 ID",
    percent,
    step,
  };
}

function inferCollectionPercent(job: AnyRecord): number {
  const status = String(job.status || "");
  const stage = String(job.stage || "");
  if (status === "succeeded" || status === "completed") return 100;
  if (status === "failed" || status === "cancelled") return 100;
  if (status === "queued") return 8;
  if (status === "cancelling") return 92;
  if (stage === "titles") return 24;
  if (stage === "screen") return 46;
  if (stage === "videos") return 68;
  if (stage === "all") return 72;
  return status === "running" ? 42 : 0;
}

function inferCollectionStep(job: AnyRecord): string {
  const status = String(job.status || "");
  const stage = String(job.stage || "");
  if (status === "succeeded" || status === "completed") return "采集流程完成，资料包与采集日志已同步";
  if (status === "failed") return "采集流程失败，请查看任务日志定位原因";
  if (status === "cancelled") return "采集任务已停止，日志已保留";
  if (status === "queued") return "任务已入队，等待采集调度";
  if (status === "cancelling") return "正在停止采集任务并收束日志";
  if (stage === "titles") return "正在采集标题池";
  if (stage === "screen") return "正在进行机会风险初筛";
  if (stage === "videos") return "正在进行视频语音处理";
  if (stage === "all") return "正在执行采集任务";
  return "正在执行采集任务";
}

function getProgressColor(percent: number, status: string) {
  if (status === "failed" || status === "cancelled") {
    return {
      barClass: "from-red-600 to-rose-500",
      dotClass: "bg-red-500",
      percentClass: "text-red-500",
    };
  }
  if (percent >= 90) {
    return {
      barClass: "from-emerald-500 to-green-400",
      dotClass: "bg-emerald-400",
      percentClass: "text-emerald-400",
    };
  }
  if (percent >= 60) {
    return {
      barClass: "from-emerald-600 to-cyan-400",
      dotClass: "bg-emerald-500",
      percentClass: "text-emerald-500",
    };
  }
  if (percent >= 30) {
    return {
      barClass: "from-amber-500 to-orange-500",
      dotClass: "bg-amber-400",
      percentClass: "text-amber-500",
    };
  }
  return {
    barClass: "from-blue-600 to-violet-500",
    dotClass: "bg-blue-500",
    percentClass: "text-blue-500",
  };
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

function GlobalSettingsPage({
  analysisColor,
  languageMode,
  onAnalysisColorChange,
  onLanguageChange,
  onPrimaryColorChange,
  onThemeChange,
  primaryColor,
  releaseStatus,
  themeMode,
}: {
  analysisColor: string;
  languageMode: LanguageMode;
  onAnalysisColorChange: (value: string) => void;
  onLanguageChange: (value: LanguageMode) => void;
  onPrimaryColorChange: (value: string) => void;
  onThemeChange: (value: ThemeMode) => void;
  primaryColor: string;
  releaseStatus: AnyRecord;
  themeMode: ThemeMode;
}) {
  const isZh = languageMode === "zh";
  return (
    <Page title={isZh ? "全局设置" : "Global Settings"} icon={<Settings className="h-5 w-5" />}>
      <section className="space-y-3">
        <h3 className="text-sm font-bold text-muted-foreground">{isZh ? "外观" : "Appearance"}</h3>
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <SettingsRow
            icon={<Monitor className="h-5 w-5" />}
            title={isZh ? "主题" : "Theme"}
          >
            <ThemeSwitch mode={themeMode} onChange={onThemeChange} languageMode={languageMode} />
          </SettingsRow>
          <SettingsRow
            icon={<Languages className="h-5 w-5" />}
            title={isZh ? "语言" : "Language"}
          >
            <SegmentedControl
              options={[
                { label: "中文", value: "zh" },
                { label: "English", value: "en" },
              ]}
              value={languageMode}
              onChange={(value) => onLanguageChange(value as LanguageMode)}
            />
          </SettingsRow>
          <SettingsRow
            description={isZh ? "自定义按钮、选中态和高亮元素的主色调。" : "Controls buttons, active states and highlighted UI."}
            icon={<Palette className="h-5 w-5" />}
            title={isZh ? "主题色" : "Theme Color"}
          >
            <ColorSwatches options={primaryColorOptions} value={primaryColor} onChange={onPrimaryColorChange} />
          </SettingsRow>
          <SettingsRow
            description={isZh ? "自定义仪表盘热力图和分析图表的主色调。" : "Controls heatmaps and analysis chart accents."}
            icon={<Activity className="h-5 w-5" />}
            title={isZh ? "分析面板主颜色" : "Analysis Panel Color"}
          >
            <ColorSwatches options={analysisColorOptions} value={analysisColor} onChange={onAnalysisColorChange} />
          </SettingsRow>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-bold text-muted-foreground">{isZh ? "关于" : "About"}</h3>
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <SettingsRow icon={<Info className="h-5 w-5" />} title={isZh ? "版本" : "Version"}>
            <span className="text-sm font-semibold text-muted-foreground">{releaseStatus.version || "V0.2.4"}</span>
          </SettingsRow>
          <SettingsRow
            description={isZh ? "本后台只监听本机地址；自动审议，不自动发布；原始证据不上传 Supabase。" : "Local-only admin. Automated review does not publish. Raw evidence is not uploaded to Supabase."}
            icon={<ShieldAlert className="h-5 w-5" />}
            title={isZh ? "声明" : "Statement"}
          >
            <Badge tone="warning">{isZh ? "本地优先" : "Local first"}</Badge>
          </SettingsRow>
          <SettingsRow
            description={isZh ? "后台运行安全状态。" : "Admin runtime security status."}
            icon={<ShieldAlert className="h-5 w-5" />}
            title={isZh ? "运行状态" : "Status"}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success">本机免登录</Badge>
              <Badge tone="warning">自动审议，不自动发布</Badge>
              <Badge tone="info">127.0.0.1</Badge>
            </div>
          </SettingsRow>
          <SettingsRow icon={<RefreshCcw className="h-5 w-5" />} title={isZh ? "检查更新" : "Check Updates"}>
            <Button variant="secondary" onClick={() => window.alert(isZh ? "当前通过 /api/v1/release/status 同步本地发布状态；GitHub Release 对齐检查会接入版本发布页。" : "Local release status is synced through /api/v1/release/status. GitHub Release alignment will be wired into the release page.")}>
              <RefreshCcw className="h-4 w-4" />
              {isZh ? "检查更新" : "Check Updates"}
            </Button>
          </SettingsRow>
        </div>
      </section>
    </Page>
  );
}

function SettingsRow({ children, description, icon, title }: { children: React.ReactNode; description?: string; icon: React.ReactNode; title: string }) {
  return (
    <div className="grid gap-3 border-b border-border px-4 py-4 last:border-b-0 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
      <div className="flex min-w-0 gap-3">
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
        <div className="min-w-0">
          <p className="text-sm font-bold">{title}</p>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 md:justify-end">{children}</div>
    </div>
  );
}

function ThemeSwitch({ mode, onChange, languageMode = "zh" }: { mode: ThemeMode; onChange: (mode: ThemeMode) => void; languageMode?: LanguageMode }) {
  const options: { icon: React.ReactNode; label: string; value: ThemeMode }[] = [
    { icon: <Monitor className="h-3.5 w-3.5" />, label: languageMode === "zh" ? "系统" : "System", value: "system" },
    { icon: <Sun className="h-3.5 w-3.5" />, label: languageMode === "zh" ? "浅色" : "Light", value: "light" },
    { icon: <Moon className="h-3.5 w-3.5" />, label: languageMode === "zh" ? "深色" : "Dark", value: "dark" }
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

function SegmentedControl({ options, value, onChange }: { options: { label: string; value: string }[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="inline-flex rounded-md bg-muted p-1 shadow-sm">
      {options.map((option) => (
        <button
          key={option.value}
          aria-pressed={value === option.value}
          className={`inline-flex min-h-9 items-center rounded px-3 text-sm font-semibold transition ${
            value === option.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ColorSwatches({ options, value, onChange }: { options: { name: string; value: string; className: string }[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {options.map((option) => (
        <button
          key={option.value}
          aria-label={option.name}
          aria-pressed={value === option.value}
          className={`h-9 w-9 rounded-full ${option.className} ${value === option.value ? "ring-4 ring-primary/30 outline outline-2 outline-foreground" : ""}`}
          onClick={() => onChange(option.value)}
          type="button"
        />
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

function CollectionStatCard({ label, value, tone }: { label: string; value: number | string; tone: "blue" | "emerald" | "rose" | "amber" }) {
  const styles = {
    blue: {
      strip: "bg-blue-500",
      value: "text-blue-500 dark:text-blue-400",
      glow: "from-blue-500/20 via-blue-500/6 to-transparent"
    },
    emerald: {
      strip: "bg-emerald-500",
      value: "text-emerald-600 dark:text-emerald-400",
      glow: "from-emerald-500/20 via-emerald-500/6 to-transparent"
    },
    rose: {
      strip: "bg-rose-500",
      value: "text-rose-600 dark:text-rose-400",
      glow: "from-rose-500/18 via-rose-500/6 to-transparent"
    },
    amber: {
      strip: "bg-amber-500",
      value: "text-amber-600 dark:text-amber-400",
      glow: "from-amber-500/18 via-amber-500/6 to-transparent"
    }
  }[tone];

  return (
    <section className="relative min-h-[148px] overflow-hidden rounded-lg border border-border/80 bg-card px-7 py-6 shadow-sm">
      <div className={`absolute left-10 top-0 h-1.5 w-20 rounded-b-md ${styles.strip}`} />
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${styles.glow}`} />
      <div className="relative">
        <p className="text-sm font-bold tracking-wide text-muted-foreground">{label}</p>
        <p className={`mt-6 text-5xl font-black leading-none tracking-normal ${styles.value}`}>{value}</p>
      </div>
    </section>
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
