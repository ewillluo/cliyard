import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CommandForm from "../CommandForm";
import { execute } from "../../api/client";

vi.mock("../../api/client", () => ({
  execute: vi.fn(),
  streamExecution: vi.fn(),
}));

/** mock schema：string + enum 下拉 + bool checkbox + file 上传 */
const schema: Record<string, unknown> = {
  type: "object",
  title: "list",
  properties: {
    name: { type: "string" },
    format: { type: "string", enum: ["json", "csv"] },
    verbose: { type: "boolean" },
    config: { type: "string", format: "binary" },
  },
  required: ["name"],
};

function renderForm(
  props: Partial<Parameters<typeof CommandForm>[0]> = {},
  onExecute = vi.fn(),
) {
  const base = {
    kind: "command" as const,
    target: "repos.list",
    schema,
    onExecute,
  };
  return render(<CommandForm {...base} {...props} />);
}

describe("CommandForm", () => {
  beforeEach(() => {
    vi.mocked(execute).mockReset();
    vi.mocked(execute).mockResolvedValue({ execution_id: "exec-1" });
  });

  it("按 schema 渲染字段：string 输入框 / enum 下拉 / bool checkbox / file 上传", () => {
    renderForm();
    expect(screen.getByTestId("run-button")).toBeInTheDocument();
    // string 输入框（label 含 required 星号，用正则匹配）
    expect(screen.getByLabelText(/name/)).toBeInTheDocument();
    // enum → select（rjsf 用索引做 option value，文本为 enum 值）
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["", "json", "csv"]);
    // bool → checkbox
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
    // file → input[type=file]
    expect(document.querySelector('input[type="file"]')).not.toBeNull();
  });

  it("点击「执行」提交表单：调 execute(kind, target, formData) 并回调 onExecute", async () => {
    const onExecute = vi.fn();
    renderForm({}, onExecute);

    fireEvent.change(screen.getByLabelText(/name/), { target: { value: "cliyard" } });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "0" } });
    fireEvent.click(screen.getByTestId("run-button"));

    await waitFor(() => expect(execute).toHaveBeenCalledTimes(1));
    expect(execute).toHaveBeenCalledWith(
      "command",
      "repos.list",
      expect.objectContaining({ name: "cliyard", format: "json" }),
    );
    await waitFor(() => expect(onExecute).toHaveBeenCalledWith("exec-1", expect.anything()));
  });

  it("schema 为 null / 空 properties 时显示「该流程无需参数」占位，提交直接 execute({})", async () => {
    const onExecute = vi.fn();
    renderForm({ schema: null }, onExecute);
    expect(screen.getByText("该流程无需参数")).toBeInTheDocument();
    // 按钮文案随 kind 变化
    expect(screen.getByTestId("run-button")).toHaveTextContent("执行");

    fireEvent.click(screen.getByTestId("run-button"));
    await waitFor(() => expect(execute).toHaveBeenCalledWith("command", "repos.list", {}));
    await waitFor(() => expect(onExecute).toHaveBeenCalledWith("exec-1", {}));
  });

  it("flow 类型按钮文案为「运行流程」", () => {
    renderForm({ kind: "flow", target: "add-user", schema: null });
    expect(screen.getByTestId("run-button")).toHaveTextContent("运行流程");
  });

  it("execute 失败显示错误提示，onExecute 不被调用", async () => {
    vi.mocked(execute).mockRejectedValue(new Error("boom"));
    const onExecute = vi.fn();
    renderForm({ schema: null }, onExecute);

    fireEvent.click(screen.getByTestId("run-button"));
    await waitFor(() => expect(screen.getByTestId("submit-error")).toBeInTheDocument());
    expect(screen.getByTestId("submit-error")).toHaveTextContent("执行失败：boom");
    expect(onExecute).not.toHaveBeenCalled();
  });

  it("重置按钮清空表单与错误提示", async () => {
    vi.mocked(execute).mockRejectedValue(new Error("boom"));
    renderForm({ schema: null });
    fireEvent.click(screen.getByTestId("run-button"));
    await waitFor(() => expect(screen.getByTestId("submit-error")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("reset-button"));
    expect(screen.queryByTestId("submit-error")).not.toBeInTheDocument();
  });
});
