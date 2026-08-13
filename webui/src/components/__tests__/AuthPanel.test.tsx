import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AuthPanel from "../AuthPanel";
import { getProfiles, switchProfile } from "../../api/client";
import type { ProfileList } from "../../api/client";

vi.mock("../../api/client", () => ({
  getProfiles: vi.fn(),
  switchProfile: vi.fn(),
}));

const getMock = vi.mocked(getProfiles);
const switchMock = vi.mocked(switchProfile);

/** 2 个 profile，当前为 dev（token 一律显示后端掩码） */
const profiles: ProfileList = {
  current: { name: "dev", endpoint: "https://api.example.com", token_masked: "tok_••••abcd" },
  profiles: [
    { name: "dev", endpoint: "https://api.example.com", token_masked: "tok_••••abcd" },
    { name: "prod", endpoint: "https://prod.example.com", token_masked: "tok_••••wxyz" },
  ],
};

function renderPanel(open = true, onClose = vi.fn()) {
  return render(<AuthPanel open={open} onClose={onClose} />);
}

describe("AuthPanel", () => {
  beforeEach(() => {
    getMock.mockReset();
    switchMock.mockReset();
    getMock.mockResolvedValue(profiles);
  });

  it("open=false 时不渲染弹层", () => {
    renderPanel(false);
    expect(screen.queryByTestId("auth-panel")).not.toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalled();
  });

  it("open=true 渲染当前 profile 与列表：name/endpoint/token 掩码，当前行高亮无切换按钮", async () => {
    renderPanel();
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(1));

    // 当前 profile 区块
    const current = screen.getByTestId("current-profile");
    expect(current).toHaveTextContent("dev");
    expect(current).toHaveTextContent("https://api.example.com");
    // token 仅显示掩码（后端 masked 值原样展示，前端不解密）
    expect(current).toHaveTextContent("tok_••••abcd");
    expect(current.textContent).not.toContain("raw-secret");

    // 列表 2 行：dev 高亮（data-active）+「当前」标签；prod 行提供「切换」按钮
    const rows = screen.getAllByTestId("profile-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute("data-active")).toBe("true");
    expect(rows[1].getAttribute("data-active")).toBe("false");
    expect(screen.getByText("当前")).toBeInTheDocument();
    const switchButtons = screen.getAllByTestId("switch-profile");
    expect(switchButtons).toHaveLength(1);
    // prod 掩码展示
    expect(screen.getByText("tok_••••wxyz")).toBeInTheDocument();
  });

  it("点击「切换」调 switchProfile(name) 并刷新列表", async () => {
    switchMock.mockResolvedValue({ current: "prod" });
    getMock
      .mockResolvedValueOnce(profiles)
      .mockResolvedValueOnce({ current: profiles.profiles[1], profiles: profiles.profiles });
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("profile-row")).toHaveLength(2));

    fireEvent.click(screen.getAllByTestId("switch-profile")[0]);
    await waitFor(() => expect(switchMock).toHaveBeenCalledWith("prod"));
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(2));

    // 刷新后 prod 变为当前（高亮 + 当前标签）
    await waitFor(() => {
      const rows = screen.getAllByTestId("profile-row");
      expect(rows[1].getAttribute("data-active")).toBe("true");
    });
  });

  it("✕ 按钮关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("auth-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Esc 键关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("点击遮罩（自身）关闭，点击面板内部不关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());

    // 面板内部点击：不关闭
    fireEvent.click(screen.getByTestId("auth-panel"));
    expect(onClose).not.toHaveBeenCalled();

    // 遮罩点击：关闭
    fireEvent.click(screen.getByTestId("auth-overlay"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("无 profile 时显示空态提示", async () => {
    getMock.mockResolvedValue({ current: null, profiles: [] });
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText("未配置 profile，请使用 cliyard auth add 添加")).toBeInTheDocument(),
    );
    expect(screen.queryAllByTestId("profile-row")).toHaveLength(0);
    expect(screen.getByTestId("current-profile")).toHaveTextContent("未选择");
  });
});
