import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import HistoryPanel from "../HistoryPanel";
import StepsPanel from "../StepsPanel";
import { listExecutions, clearExecutions, replayExecution, streamExecution } from "../../api/client";
import type { HistoryItem } from "../../api/client";

vi.mock("../../api/client", () => ({
  listExecutions: vi.fn(),
  clearExecutions: vi.fn(),
  replayExecution: vi.fn(),
  execute: vi.fn(),
  streamExecution: vi.fn(),
}));

const listMock = vi.mocked(listExecutions);
const clearMock = vi.mocked(clearExecutions);
const replayMock = vi.mocked(replayExecution);

/** 3 条历史：done / error / running 各一（覆盖全部状态 pill 与耗时格式） */
const items: HistoryItem[] = [
  {
    id: "e1",
    created_at: "2026-08-13T14:23:01.204123+08:00",
    kind: "command",
    target: "repos.list",
    status: "done",
    duration_ms: 129,
    result_preview: "",
  },
  {
    id: "e2",
    created_at: "2026-08-13T14:18:12.000123+08:00",
    kind: "command",
    target: "users.reset-pwd",
    status: "error",
    duration_ms: 1240,
    result_preview: "",
  },
  {
    id: "e3",
    created_at: "2026-08-13T14:10:03.500123+08:00",
    kind: "flow",
    target: "add-user",
    status: "running",
    duration_ms: null,
    result_preview: "",
  },
];

function renderHistory(onReExecute = vi.fn()) {
  return render(<HistoryPanel onReExecute={onReExecute} />);
}

describe("HistoryPanel", () => {
  beforeEach(() => {
    listMock.mockReset();
    clearMock.mockReset();
    replayMock.mockReset();
    vi.mocked(streamExecution).mockReset();
    listMock.mockResolvedValue({ total: items.length, items });
  });

  it("挂载即加载并渲染历史表格：时间 HH:MM:SS、命令资源名高亮、状态 pill、耗时格式化", async () => {
    renderHistory();
    await waitFor(() => expect(listMock).toHaveBeenCalledWith(20, 0));

    const rows = screen.getAllByTestId("history-row");
    expect(rows).toHaveLength(3);
    // 开始时间
    expect(screen.getByText("14:23:01")).toBeInTheDocument();
    // 命令："repos.list" → 资源名 repos 品牌蓝 + .list 深色（split 两个 span）
    expect(screen.getByText("repos")).toBeInTheDocument();
    expect(screen.getByText(".list")).toBeInTheDocument();
    // 状态 pill：成功/失败/执行中
    expect(screen.getByText("成功")).toBeInTheDocument();
    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(screen.getByText("执行中")).toBeInTheDocument();
    // 耗时：129ms / 1.2s（≥1000 转秒）/ 空值 —（running 无终态）
    expect(screen.getByText("129ms")).toBeInTheDocument();
    expect(screen.getByText("1.2s")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    // 分页统计
    expect(screen.getByTestId("history-count")).toHaveTextContent("共 3 条 · 第 1 / 1 页");
  });

  it("状态 pill 携带 data-status：done→成功 / error→失败 / running→执行中", async () => {
    renderHistory();
    await waitFor(() => expect(screen.getAllByTestId("history-row")).toHaveLength(3));
    const pills = screen.getAllByTestId("history-status");
    expect(pills.map((p) => p.getAttribute("data-status"))).toEqual(["done", "error", "running"]);
  });

  it("重放：replayExecution(id) 成功后回调 onReExecute(新 execution_id)", async () => {
    replayMock.mockResolvedValue({ execution_id: "e4" });
    const onReExecute = vi.fn();
    renderHistory(onReExecute);
    await waitFor(() => expect(screen.getAllByTestId("replay-button")).toHaveLength(3));

    fireEvent.click(screen.getAllByTestId("replay-button")[0]);
    await waitFor(() => expect(replayMock).toHaveBeenCalledWith("e1"));
    await waitFor(() => expect(onReExecute).toHaveBeenCalledWith("e4"));
  });

  it("分页：每页 20，下一页带 offset 20 重新请求，首页禁用上一页", async () => {
    listMock.mockResolvedValue({ total: 45, items: items.slice(0, 2) });
    renderHistory();
    await waitFor(() => expect(screen.getByTestId("history-count")).toHaveTextContent("共 45 条 · 第 1 / 3 页"));
    expect(screen.getByTestId("history-prev")).toBeDisabled();

    fireEvent.click(screen.getByTestId("history-next"));
    await waitFor(() => expect(listMock).toHaveBeenLastCalledWith(20, 20));
    expect(screen.getByTestId("history-count")).toHaveTextContent("第 2 / 3 页");
    expect(screen.getByTestId("history-prev")).not.toBeDisabled();
  });

  it("空列表显示空态「暂无执行历史」", async () => {
    listMock.mockResolvedValue({ total: 0, items: [] });
    renderHistory();
    await waitFor(() => expect(screen.getByText("暂无执行历史")).toBeInTheDocument());
    expect(screen.getByTestId("history-count")).toHaveTextContent("共 0 条 · 第 1 / 1 页");
  });

  it("StepsPanel 内「清空记录」：调 clearExecutions 后重新加载并回到第 1 页", async () => {
    clearMock.mockResolvedValue(undefined);
    vi.mocked(streamExecution).mockReturnValue(vi.fn());
    render(<StepsPanel executionId={null} onReExecute={vi.fn()} />);

    fireEvent.click(screen.getAllByTestId("panel-tab")[1]);
    await waitFor(() => expect(screen.getAllByTestId("history-row")).toHaveLength(3));

    // 清空后返回空列表（重新加载）
    listMock.mockResolvedValue({ total: 0, items: [] });
    fireEvent.click(screen.getByTestId("clear-history-button"));
    await waitFor(() => expect(clearMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("暂无执行历史")).toBeInTheDocument());
  });

  it("StepsPanel 内「刷新」：重新调用 listExecutions 加载当前页", async () => {
    vi.mocked(streamExecution).mockReturnValue(vi.fn());
    render(<StepsPanel executionId={null} onReExecute={vi.fn()} />);

    fireEvent.click(screen.getAllByTestId("panel-tab")[1]);
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId("refresh-history-button"));
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
    expect(listMock.mock.calls[1][0]).toBe(20);
    expect(listMock.mock.calls[1][1]).toBe(0);
  });

  it("历史重放回调后 StepsPanel 切回「执行步骤」tab", async () => {
    replayMock.mockResolvedValue({ execution_id: "e4" });
    vi.mocked(streamExecution).mockReturnValue(vi.fn());
    render(<StepsPanel executionId={null} onReExecute={vi.fn()} />);

    fireEvent.click(screen.getAllByTestId("panel-tab")[1]);
    await waitFor(() => expect(screen.getAllByTestId("replay-button")).toHaveLength(3));

    fireEvent.click(screen.getAllByTestId("replay-button")[0]);
    await waitFor(() => expect(screen.getByTestId("re-run-button")).toBeInTheDocument());
    const tabs = screen.getAllByTestId("panel-tab");
    expect(tabs[0].getAttribute("data-active")).toBe("true");
  });
});
