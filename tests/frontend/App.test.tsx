import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../web-admin/src/App";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/dashboard/summary")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
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
        json: () => Promise.resolve({ version: "V0.2.4", checklist: ["运行测试"] })
      });
    }
    if (url.includes("/api/v1/collection/jobs")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [
              {
                id: "job-running-test",
                platform: "xiaohongshu",
                stage: "titles",
                status: "running",
                dry_run: false
              }
            ]
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
  it("renders fixed Chinese title and switches independent pages", async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getByRole("heading", { name: "以太情报后台" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "采集优先的阳朔旅游情报后台" })).not.toBeInTheDocument();
    expect(screen.getByText("自动审议，不自动发布")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "采集作战台" })).toBeInTheDocument();
    expect(screen.getAllByText("采集标题池").length).toBeGreaterThan(0);
    expect(screen.getAllByText("完整采集流程").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "停止" })).toBeInTheDocument();

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
  });
});
