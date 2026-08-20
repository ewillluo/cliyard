import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import StepsPanel from "../StepsPanel";
import { streamExecution, listExecutions } from "../../api/client";
import type { ExecutionEvent } from "../../api/client";

vi.mock("../../api/client", () => ({
  streamExecution: vi.fn(),
  execute: vi.fn(),
  listExecutions: vi.fn(),
  clearExecutions: vi.fn(),
  replayExecution: vi.fn(),
}));

const streamMock = vi.mocked(streamExecution);

/** 命令事件序列：validate → request → done */
const commandEvents: ExecutionEvent[] = [
  {
    type: "validate",
    time: "2026-08-13T14:23:01.204123+08:00",
    params: { query: { page_size: 20 }, body: { name: "cliyard" } },
  },
  {
    type: "request",
    time: "2026-08-13T14:23:01.206123+08:00",
    method: "GET",
    url: "https://api.example.com/api/v1/repos",
    headers: { Authorization: "Bearer ••••" },
  },
  {
    type: "done",
    time: "2026-08-13T14:23:01.500123+08:00",
    status: "done",
    duration_ms: 296,
  },
];

/** flow 事件序列：step_start → step_done → flow_end → done */
const flowEvents: ExecutionEvent[] = [
  {
    type: "step_start",
    time: "2026-08-13T14:30:01.110123+08:00",
    index: 1,
    id: "check_user",
    label: "check_user",
    use: "user.list",
  },
  {
    type: "step_done",
    time: "2026-08-13T14:30:01.204123+08:00",
    index: 1,
    id: "check_user",
    label: "check_user",
    status: "ok",
    elapsed_ms: 94,
    result_preview: '{"found_users": []}',
  },
  {
    type: "flow_end",
    time: "2026-08-13T14:30:01.900123+08:00",
    outcome: "completed",
    step_count: 1,
  },
  {
    type: "done",
    time: "2026-08-13T14:30:01.901123+08:00",
    status: "done",
    duration_ms: 800,
  },
];

function renderPanel(
  executionId: string | null = "exec-1",
  onReExecute = vi.fn(),
) {
  return render(<StepsPanel executionId={executionId} onReExecute={onReExecute} />);
}

describe("StepsPanel", () => {
  beforeEach(() => {
    streamMock.mockReset();
    vi.mocked(listExecutions).mockReset();
  });

  it("命令执行：validate→request→done 合并为单张「执行结果」卡片，显示耗时和请求详情", () => {
    streamMock.mockImplementation((_id, onEvent) => {
      commandEvents.forEach(onEvent);
      return vi.fn();
    });
    renderPanel();

    // 单张卡片，标题为「执行结果」
    expect(screen.getByText("执行结果")).toBeInTheDocument();
    // 时间 pill（来自 done 事件的时间）
    expect(screen.getByText("14:23:01.500")).toBeInTheDocument();
    // 耗时显示在摘要行（badge 和摘要行各一处）
    expect(screen.getAllByText("耗时 296ms")).toHaveLength(2);
    // done 事件 → loading 停止：无「执行中」pill
    expect(screen.queryByText("执行中")).not.toBeInTheDocument();
    // 顶部 badge：耗时
    expect(screen.getByTestId("steps-badge")).toHaveTextContent("耗时 296ms");
    // 图标：完成状态
    const icons = screen.getAllByTestId("step-icon");
    expect(icons).toHaveLength(1);
    expect(icons[0].getAttribute("data-status")).toBe("done");
    // 请求详情折叠面板（含 validate + request 2 个 pipeline 事件）
    expect(screen.getByText("请求详情（2）")).toBeInTheDocument();
  });

  it("命令执行 error：错误信息+失败 pill+红色图标+loading 停止", () => {
    streamMock.mockImplementation((_id, onEvent) => {
      (
        [
          { type: "validate", time: "2026-08-13T14:23:01.204123+08:00", params: {} },
          {
            type: "error",
            time: "2026-08-13T14:23:01.300123+08:00",
            message: "Connection refused",
          },
        ] as ExecutionEvent[]
      ).forEach(onEvent);
      return vi.fn();
    });
    renderPanel();

    // 标题「执行结果」
    expect(screen.getByText("执行结果")).toBeInTheDocument();
    expect(screen.getByText("失败")).toBeInTheDocument();
    // 错误信息在摘要行（格式：错误: xxx）
    expect(screen.getByText("错误: Connection refused")).toBeInTheDocument();
    expect(screen.queryByText("执行中")).not.toBeInTheDocument();
    const icons = screen.getAllByTestId("step-icon");
    expect(icons).toHaveLength(1);
    expect(icons[0].getAttribute("data-status")).toBe("error");
  });

  it("flow 事件显示编排步骤进度 badge 与步骤标题（步骤 N · label）", () => {
    streamMock.mockImplementation((_id, onEvent) => {
      flowEvents.forEach(onEvent);
      return vi.fn();
    });
    renderPanel();

    // step_start + step_done 合并为一张「步骤 1 · check_user」卡片（不重复展示），
    // 卡片内容 = use 行 + 结果行（elapsed / result_preview）
    expect(screen.getAllByText("步骤 1 · check_user")).toHaveLength(1);
    // summaryLines 渲染为 div，非 pre
    expect(screen.getByText("use: user.list")).toBeInTheDocument();
    expect(screen.getByText("耗时 94ms")).toBeInTheDocument();
    expect(screen.getByText("found_users: []")).toBeInTheDocument();
    expect(screen.getByTestId("steps-badge")).toHaveTextContent("编排步骤 1/1");
  });

  it("executionId 变化重新订阅（取消旧流）", () => {
    const cancel = vi.fn();
    streamMock.mockImplementation((_id, onEvent) => {
      commandEvents.forEach(onEvent);
      return cancel;
    });
    const { rerender } = renderPanel("exec-1");
    expect(streamMock).toHaveBeenCalledTimes(1);

    rerender(<StepsPanel executionId="exec-2" onReExecute={vi.fn()} />);
    expect(streamMock).toHaveBeenCalledTimes(2);
    expect(streamMock.mock.calls[1][0]).toBe("exec-2");
    expect(cancel).toHaveBeenCalled();
  });

  it("重新执行 / 复制 / 清空按钮行为", async () => {
    streamMock.mockImplementation((_id, onEvent) => {
      commandEvents.forEach(onEvent);
      return vi.fn();
    });
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    const onReExecute = vi.fn();
    renderPanel("exec-1", onReExecute);

    // 重新执行 → 回调父级
    fireEvent.click(screen.getByTestId("re-run-button"));
    expect(onReExecute).toHaveBeenCalled();

    // 复制 → clipboard 写入步骤文本
    fireEvent.click(screen.getByTestId("copy-button"));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    expect(screen.getByTestId("copy-button")).toHaveTextContent("已复制");

    // 清空 → 步骤消失（executionId 仍在，显示等待事件空态）
    fireEvent.click(screen.getByTestId("clear-button"));
    expect(screen.queryByText("参数校验")).not.toBeInTheDocument();
    expect(screen.getByText("等待执行事件…")).toBeInTheDocument();
  });

  it("无 executionId 时显示空态占位", () => {
    renderPanel(null);
    expect(screen.getByText("执行命令后此处显示步骤流")).toBeInTheDocument();
  });

  it("历史 tab 渲染执行历史列表（T11）", async () => {
    vi.mocked(listExecutions).mockResolvedValue({
      total: 1,
      items: [
        {
          id: "e1",
          created_at: "2026-08-13T14:23:01.204123+08:00",
          kind: "command",
          target: "repos.list",
          status: "done",
          duration_ms: 129,
          result_preview: "",
        },
      ],
    });
    renderPanel(null);
    fireEvent.click(screen.getAllByTestId("panel-tab")[1]);
    await waitFor(() => expect(screen.getByTestId("history-row")).toBeInTheDocument());
    expect(screen.getByText("14:23:01")).toBeInTheDocument();
    expect(screen.getByText("共 1 条 · 第 1 / 1 页")).toBeInTheDocument();
    // tab bar 提供清空/刷新按钮
    expect(screen.getByTestId("clear-history-button")).toBeInTheDocument();
    expect(screen.getByTestId("refresh-history-button")).toBeInTheDocument();
  });

  it("format 事件带 table 时默认渲染表格视图（alias 列头 + 行值），可切换 JSON", () => {
    const formatWithTable: ExecutionEvent = {
      type: "format",
      time: "2026-08-13T14:23:01.400123+08:00",
      output_preview: '{"repos":[{"name":"a","type":"EVENTS"},{"name":"b","type":"LOGS"}]}',
      table: {
        columns: [
          { name: "name", alias: "仓库名称" },
          { name: "type", alias: "仓库类型" },
        ],
        rows: [
          ["a", "EVENTS"],
          ["b", "LOGS"],
        ],
        total: 2,
      },
    };
    streamMock.mockImplementation((_id, onEvent) => {
      [commandEvents[0], formatWithTable].forEach(onEvent);
      return vi.fn();
    });
    renderPanel();

    // 默认表格视图：alias 列头 + 行值 + total 提示
    expect(screen.getByText("仓库名称")).toBeInTheDocument();
    expect(screen.getByText("仓库类型")).toBeInTheDocument();
    expect(screen.getByText("EVENTS")).toBeInTheDocument();
    expect(screen.getByText("LOGS")).toBeInTheDocument();
    expect(screen.getByText("共 2 条")).toBeInTheDocument();

    // 切换 JSON → 显示 output_preview 文本，表格消失
    fireEvent.click(screen.getByTestId("format-view-json"));
    expect(screen.getByText(/"repos"/)).toBeInTheDocument();
    expect(screen.queryByText("仓库名称")).not.toBeInTheDocument();

    // 切回表格
    fireEvent.click(screen.getByTestId("format-view-table"));
    expect(screen.getByText("仓库名称")).toBeInTheDocument();
  });

  it("format 事件无 table 时显示纯 JSON", () => {
    const formatPlain: ExecutionEvent = {
      type: "format",
      time: "2026-08-13T14:23:01.400123+08:00",
      output_preview: '{"items":[{"name":"a"}]}',
    };
    streamMock.mockImplementation((_id, onEvent) => {
      [commandEvents[0], formatPlain].forEach(onEvent);
      return vi.fn();
    });
    renderPanel();

    expect(screen.queryByText("表格")).not.toBeInTheDocument();
    expect(screen.queryByText("JSON")).not.toBeInTheDocument();
    // formatLines 输出在卡片摘要行（通过 formatLines 展示）
    expect(screen.getByText(/"items"/)).toBeInTheDocument();
  });
});
