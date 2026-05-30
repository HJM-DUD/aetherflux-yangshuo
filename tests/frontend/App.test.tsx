import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../web-admin/src/App";

const fetchMock = vi.fn();

function defaultConfigPayload() {
  return {
    platforms: ["xiaohongshu", "douyin"],
    manual_queries: ["阳朔 旅游"],
    segments: ["景区"],
    risk_terms: ["避雷"],
    opportunity_terms: ["攻略"],
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
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-mode");
  document.documentElement.classList.remove("dark");
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn()
    }))
  });
  fetchMock.mockReset();
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/dashboard/summary")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            version: "V0.2.7",
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
            }
          })
      });
    }
    if (url.includes("/api/v1/collection/config")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            platforms: ["xiaohongshu", "douyin"],
            manual_queries: ["阳朔 旅游"],
            segments: ["景区"],
            risk_terms: ["避雷"],
            opportunity_terms: ["攻略"],
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
          })
      });
    }
    if (url.includes("/api/v1/release/status")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ current_version: "V0.2.7", checklist: ["运行测试"] })
      });
    }
    if (url.includes("/api/v1/collection/jobs")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: Array.from({ length: 9 }, (_, index) => ({
              id: `job-${index + 1}`,
              platform: index % 2 === 0 ? "xiaohongshu" : "douyin",
              stage: index === 0 ? "all" : index === 1 ? "videos" : "titles",
              mode: index % 2 === 0 ? "shellCLI" : "agentCLI",
              action: index === 0 ? "collect" : index === 1 ? "package" : "clean",
              status: index === 0 ? "running" : "succeeded",
              dry_run: false,
              started_at: "2026-05-30T08:00:00Z",
              log_size_bytes: 2048,
              items_collected: index === 0 ? 31 : 0
            }))
          })
      });
    }
    if (url.includes("/api/v1/title-pool")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [],
            empty_reason: "no_matching_files",
            collected_at: "2026-05-30T08:15:00Z"
          })
      });
    }
    if (url.includes("/api/v1/admin/retention")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            evidence_hours: 48,
            cloud_log_months: 3,
            notice: "原始截图、HTML、音视频、评论全文和完整转写不上传 Supabase Cloud。"
          })
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [] })
    });
  });
  global.fetch = fetchMock as any;
});

describe("V0.2.4 admin app", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders fixed Chinese title and switches independent pages", async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getByRole("heading", { name: "以太情报后台" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "采集优先的阳朔旅游情报后台" })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "采集操作台" })).toBeInTheDocument();
    expect(screen.getByText("采集目标")).toBeInTheDocument();
    expect(screen.getAllByText("采集模式一（脚本主导）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("采集模式二（Agent主导）").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "网页手动启动" }).length).toBe(2);
    expect(screen.getAllByRole("button", { name: "启动采集" }).length).toBe(2);
    expect(screen.getAllByRole("button", { name: "停止" }).length).toBeGreaterThan(1);
    expect(screen.getByText("清理数据")).toBeInTheDocument();
    expect(screen.getByText("生成资料包")).toBeInTheDocument();
    expect(screen.getAllByText("运行中").length).toBeGreaterThan(0);
    expect(screen.getAllByText("已完成").length).toBeGreaterThan(0);
    expect(screen.queryByText("当前阶段")).not.toBeInTheDocument();
    expect(screen.queryByText("running")).not.toBeInTheDocument();
    expect(screen.queryByText("succeeded")).not.toBeInTheDocument();
    expect(screen.queryByText("Dry-run")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "启动完整采集流程" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "采集标题池" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "机会风险初筛" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "视频语音处理" })).not.toBeInTheDocument();
    expect(screen.getByText("整体采集进度")).toBeInTheDocument();
    expect(screen.getByText("正在执行采集任务")).toBeInTheDocument();
    expect(screen.getByText("72%")).toHaveClass("text-emerald-500");
    expect(screen.getByTestId("collection-progress-fill")).toHaveStyle({ width: "72%" });
    expect(screen.getByText("候选情报").closest("section")).toHaveClass("min-h-[148px]", "overflow-hidden", "rounded-lg");
    expect(screen.getByText("风险预警").nextElementSibling).toHaveClass("text-rose-600");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "采集配置" }));
    });
    expect(screen.getByRole("heading", { name: "采集配置" })).toBeInTheDocument();
    expect(screen.getByText("新鲜度窗口小时")).toBeInTheDocument();
    expect(screen.getByText("ASR 后端")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "标题池" }));
    });
    expect(screen.getByRole("heading", { name: "标题池" })).toBeInTheDocument();
    expect(screen.getByText(/暂无标题池数据/)).toBeInTheDocument();
    expect(screen.queryByText(/no_matching_files/)).not.toBeInTheDocument();
    expect(screen.getByText(/采集日期/)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "语音转文字深处理" }));
    });
    expect(screen.getByRole("heading", { name: "语音转文字深处理" })).toBeInTheDocument();
    expect(screen.getByText(/暂无 ASR 结果/)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "软删除回收站" }));
    });
    expect(screen.getByRole("heading", { name: "软删除回收站" })).toBeInTheDocument();
    expect(screen.getByText(/回收站为空/)).toBeInTheDocument();
    expect(screen.queryByText("V0.2.4 Web Admin")).not.toBeInTheDocument();
    expect(screen.queryByText("Freshness")).not.toBeInTheDocument();
  }, 10000);

  it("keeps the sidebar fixed, collapsible, grouped, and pins utility pages at the bottom", async () => {
    await act(async () => {
      render(<App />);
    });

    const sidebar = screen.getByTestId("admin-sidebar");
    expect(sidebar).toHaveClass("sticky", "top-0", "h-dvh", "shrink-0");
    expect(sidebar).not.toHaveClass("lg:sticky");
    expect(screen.getByText("采集控制")).toBeInTheDocument();
    expect(screen.getByText("情报处理")).toBeInTheDocument();
    expect(screen.getByText("核验信源")).toBeInTheDocument();
    expect(screen.getByText("输出接口")).toBeInTheDocument();
    expect(screen.getByText("数据治理")).toBeInTheDocument();

    const utilityNav = screen.getByTestId("sidebar-utility-nav");
    expect(within(utilityNav).getByRole("button", { name: "系统诊断" })).toBeInTheDocument();
    expect(within(utilityNav).getByRole("button", { name: "版本发布" })).toBeInTheDocument();
    expect(within(utilityNav).getByRole("button", { name: "全局设置" })).toBeInTheDocument();
    expect(within(sidebar).queryByRole("button", { name: "折叠菜单" })).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "折叠菜单" }));
    });

    expect(sidebar).toHaveClass("w-[88px]");
    expect(screen.queryByText("AetherFlux · V0.2.4")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开菜单" })).toBeInTheDocument();
  });

  it("moves appearance controls into global settings and supports English shell labels", async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.queryByRole("button", { name: "浅色" })).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "全局设置" }));
    });

    expect(screen.getByRole("heading", { name: "全局设置" })).toBeInTheDocument();
    expect(screen.getByText("外观")).toBeInTheDocument();
    expect(screen.getByText("主题")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "浅色" })).toBeInTheDocument();
    expect(screen.getByText("语言")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
    expect(screen.getByText("主题色")).toBeInTheDocument();
    expect(screen.getByText("分析面板主颜色")).toBeInTheDocument();
    expect(screen.getByText("关于")).toBeInTheDocument();
    expect(screen.getAllByText("检查更新").length).toBeGreaterThan(0);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "English" }));
    });

    expect(screen.getByRole("heading", { name: "Global Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collection Console" })).toBeInTheDocument();
    expect(screen.getByText("Theme")).toBeInTheDocument();
    expect(localStorage.getItem("aetherflux-admin-language")).toBe("en");
  });

  it("uses restrained color blocks and reserves red for true warnings", async () => {
    await act(async () => {
      render(<App />);
    });

    // Badges now live in global settings
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "全局设置" }));
    });

    expect(await screen.findByText("本机免登录")).toHaveClass("bg-emerald-600", "text-white");
    expect(screen.getByText("127.0.0.1")).toHaveClass("bg-primary", "text-primary-foreground");
    expect(screen.getByText("自动审议，不自动发布")).toHaveClass("bg-white", "text-red-500");
    expect(screen.getByText("自动审议，不自动发布")).not.toHaveClass("border-red-500");

    // Platform/status badges are on collection console
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "采集操作台" }));
    });

    expect(screen.getAllByText("小红书")[0]).toHaveClass("bg-primary", "text-primary-foreground");
    expect(screen.getAllByText("♪").length).toBeGreaterThan(0);
    expect(screen.getAllByText("运行中")[0]).toHaveClass("bg-primary", "text-primary-foreground");
    expect(screen.getByRole("button", { name: "语音转文字深处理" })).toBeInTheDocument();
  });

  it("switches between light and dark themes from global settings", async () => {
    await act(async () => {
      render(<App />);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "全局设置" }));
    });

    expect(await screen.findByRole("button", { name: "浅色" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "深色" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "系统" })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "深色" }));
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("aetherflux-admin-theme")).toBe("dark");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "浅色" }));
    });
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement).not.toHaveClass("dark");
    expect(localStorage.getItem("aetherflux-admin-theme")).toBe("light");
  });

  it("uses configured platforms and submits collection mode jobs with manual or automatic flow", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    await act(async () => {
      render(<App />);
    });

    expect((await screen.findAllByText("小红书")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("抖音").length).toBeGreaterThan(0);

    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "启动采集" })[0]);
    });

    const jobPosts = fetchMock.mock.calls.filter(([url, init]) => String(url).includes("/api/v1/collection/jobs") && (init as RequestInit | undefined)?.method === "POST");
    expect(jobPosts).toHaveLength(1);
    expect(JSON.parse(String((jobPosts[0][1] as RequestInit).body))).toMatchObject({
      platform: "xiaohongshu,douyin",
      stage: "all",
      mode: "shellCLI",
      action: "collect",
      run_mode: "manual",
      dry_run: false
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "自动执行" }));
    });
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "自动三步" })[1]);
    });

    const nextJobPosts = fetchMock.mock.calls.filter(([url, init]) => String(url).includes("/api/v1/collection/jobs") && (init as RequestInit | undefined)?.method === "POST");
    expect(nextJobPosts).toHaveLength(2);
    expect(JSON.parse(String((nextJobPosts[1][1] as RequestInit).body))).toMatchObject({
      platform: "xiaohongshu,douyin",
      mode: "agentCLI",
      action: "auto_pipeline",
      run_mode: "auto"
    });
  });

  it("paginates the job queue and refreshes it every five seconds when a job is active", async () => {
    await act(async () => {
      render(<App />);
    });

    const queue = await screen.findByTestId("collection-job-table");
    expect(within(queue).getByText("job-1…")).toBeInTheDocument();
    expect(within(queue).queryByText("job-9…")).not.toBeInTheDocument();
    expect(screen.getByText(/第 1\/2 页/)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "下页" }));
    });
    expect(within(queue).getByText("job-9…")).toBeInTheDocument();

    const before = fetchMock.mock.calls.length;
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 5100));
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(before);
  }, 8000);

  it("slows collection polling to thirty seconds when no job is active", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/dashboard/summary")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: "V0.2.7", counts: {} }) });
      }
      if (url.includes("/api/v1/collection/config")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(defaultConfigPayload()) });
      }
      if (url.includes("/api/v1/collection/jobs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ items: [{ id: "job-idle", status: "succeeded", platform: "douyin", mode: "shellCLI", action: "collect" }] })
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });

    await act(async () => {
      render(<App />);
      await Promise.resolve();
    });

    const before = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });
    expect(fetchMock.mock.calls.length).toBe(before);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(24900);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(before);
  });

  it("filters title pool items by fuzzy search text", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/collection/config")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              platforms: ["xiaohongshu", "douyin"],
              manual_queries: [],
              segments: [],
              risk_terms: [],
              opportunity_terms: [],
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
            })
        });
      }
      if (url.includes("/api/v1/title-pool")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                { title: "阳朔竹筏排队明显增加", platform: "xiaohongshu", keyword: "竹筏", status: "待处理" },
                { title: "西街夜游热度上升", platform: "douyin", keyword: "西街", status: "待处理" }
              ],
              collected_at: "2026-05-30T08:15:00Z"
            })
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] })
      });
    });

    await act(async () => {
      render(<App />);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "标题池" }));
    });
    expect(screen.getByText("阳朔竹筏排队明显增加")).toBeInTheDocument();
    expect(screen.getByText("西街夜游热度上升")).toBeInTheDocument();

    await act(async () => {
      fireEvent.change(screen.getByLabelText("检索标题池"), { target: { value: "竹筏" } });
    });

    expect(screen.getByText("阳朔竹筏排队明显增加")).toBeInTheDocument();
    expect(screen.queryByText("西街夜游热度上升")).not.toBeInTheDocument();
  });

  it("renders cross-check records as Chinese review cards instead of raw JSON", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/intelligence/candidates")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "cross-1",
                  title: "阳朔酒店推广热度异常",
                  platform: "xiaohongshu",
                  score: 86,
                  cross_check: {
                    status: "unverified",
                    supporting_sources: [
                      "https://www.xiaohongshu.com/search_result/abc123?xsec_source=pc_search",
                      "https://example.com/source"
                    ],
                    conflicting_sources: [],
                    needs_more_sources: true,
                    reasoning: "Multiple posts from Xiaohongshu about the same hotel suggest a coordinated marketing effort, but without independent reviews, authenticity is questionable."
                  }
                }
              ]
            })
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] })
      });
    });

    await act(async () => {
      render(<App />);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "交叉验证" }));
    });

    expect(screen.getByRole("heading", { name: "交叉验证" })).toBeInTheDocument();
    expect(screen.getByText("阳朔酒店推广热度异常")).toBeInTheDocument();
    expect(screen.getByText("未验证")).toHaveClass("bg-white", "text-red-500");
    expect(screen.getByText("需要补证")).toBeInTheDocument();
    expect(screen.getByText("支持来源")).toBeInTheDocument();
    expect(screen.getByText("https://www.xiaohongshu.com/search_result/abc123?xsec_source=pc_search")).toBeInTheDocument();
    expect(screen.queryByText("来源已脱敏")).not.toBeInTheDocument();
    expect(screen.getByText("冲突来源")).toBeInTheDocument();
    expect(screen.getByText("暂无冲突来源")).toBeInTheDocument();
    expect(screen.getByText(/小红书上多条同类内容相互印证/)).toBeInTheDocument();
    expect(screen.queryByText(/supporting_sources/)).not.toBeInTheDocument();
    expect(screen.queryByText(/[{}]/)).not.toBeInTheDocument();
  });

  it("groups candidate review items by human decision, translation, score and geo risk", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/intelligence/decisions") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              ok: true,
              candidate: {
                id: body.id,
                title: "English title about Yangshuo rafting",
                display: { title_zh: "阳朔竹筏英文选题", summary_zh: "中文翻译摘要" },
                platform: "xiaohongshu",
                human_status: body.status,
                score: 86,
                geo_risk: { probability: 0.76, level: "high", reasons: ["同质化回答集中出现"] }
              }
            })
        });
      }
      if (url.includes("/api/v1/trash/restore") && init?.method === "POST") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ restored: 1 }) });
      }
      if (url.includes("/api/v1/trash") && init?.method === "POST") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ moved: 1 }) });
      }
      if (url.includes("/api/v1/intelligence/candidates")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "candidate-en",
                  title: "English title about Yangshuo rafting",
                  summary: "Original English summary",
                  display: { title_zh: "阳朔竹筏英文选题", summary_zh: "中文翻译摘要" },
                  platform: "xiaohongshu",
                  human_status: "pending",
                  score: 86,
                  tags: ["竹筏", "排队"],
                  geo_risk: { probability: 0.76, level: "high", reasons: ["同质化回答集中出现"] }
                },
                {
                  id: "candidate-rejected",
                  title: "Rejected source title",
                  summary: "Rejected source summary",
                  display: { title_zh: "已驳回测试议题", summary_zh: "已驳回测试摘要" },
                  platform: "douyin",
                  human_status: "rejected",
                  score: 28,
                  tags: ["竹筏", "避雷"]
                }
              ]
            })
        });
      }
      if (url.includes("/api/v1/trash")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] })
      });
    });

    await act(async () => {
      render(<App />);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "候选审阅" }));
    });

    expect(screen.getByRole("heading", { name: "候选待确认" })).toBeInTheDocument();
    expect(screen.getAllByText("原文").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("candidate-original-panel")[0]).toHaveClass("bg-slate-950", "text-white");
    expect(screen.getByText("English title about Yangshuo rafting")).toBeInTheDocument();
    expect(screen.getAllByText("翻译").length).toBeGreaterThan(0);
    expect(screen.getByText("阳朔竹筏英文选题")).toBeInTheDocument();
    expect(screen.getAllByText("标签热度").length).toBeGreaterThan(0);
    expect(screen.getAllByText("竹筏 ×2")[0]).toHaveClass("bg-red-600", "text-white");
    expect(screen.getByText("排队 ×1")).toHaveClass("bg-emerald-100", "text-emerald-900");
    expect(screen.getByText("小红书")).toHaveClass("bg-primary", "text-primary-foreground");
    expect(screen.getByText("待确认")).toHaveClass("bg-primary", "text-primary-foreground");
    const rejectedStatus = screen.getAllByText("已驳回").find((element) => element.tagName.toLowerCase() === "span");
    expect(rejectedStatus).toHaveClass("bg-danger", "text-white");
    expect(screen.getByText("86")).toHaveClass("bg-emerald-600", "text-white");
    expect(screen.getAllByText("生成式搜索风险").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("76%")).toHaveClass("text-red-600");
    expect(screen.getByText("高风险")).toBeInTheDocument();
    expect(screen.getByText("0%")).toHaveClass("text-emerald-600");
    expect(screen.getByText("极小风险")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "确认" })[0]);
    });

    expect(screen.getByRole("heading", { name: "已确认" })).toBeInTheDocument();
    expect(screen.getByText("候选待确认暂无议题。")).toBeInTheDocument();
    expect(screen.getByText("当日选题已人工确认完毕")).toBeInTheDocument();
  });
});
