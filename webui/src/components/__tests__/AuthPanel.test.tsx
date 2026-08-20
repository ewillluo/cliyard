import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AuthPanel from "../AuthPanel";
import { getProfiles, switchProfile, loginAuth, refreshAuth, deleteAuth, fetchEnvironments } from "../../api/client";
import type { ProfileList } from "../../api/client";

vi.mock("../../api/client", () => ({
  getProfiles: vi.fn(),
  switchProfile: vi.fn(),
  loginAuth: vi.fn(),
  refreshAuth: vi.fn(),
  deleteAuth: vi.fn(),
  fetchEnvironments: vi.fn(),
}));

const getMock = vi.mocked(getProfiles);
const switchMock = vi.mocked(switchProfile);
const loginMock = vi.mocked(loginAuth);
const refreshMock = vi.mocked(refreshAuth);
const deleteMock = vi.mocked(deleteAuth);
const envMock = vi.mocked(fetchEnvironments);

const profiles: ProfileList = {
  current: { name: "staging-admin", endpoint: "https://api.staging.example.com", token_masked: "\u2022\u2022\u2022\u2022abcd", expires_at: 4939556089 },
  profiles: [
    { name: "staging-admin", endpoint: "https://api.staging.example.com", token_masked: "\u2022\u2022\u2022\u2022abcd", expires_at: 4939556089 },
    { name: "prod-admin", endpoint: "https://api.prod.example.com", token_masked: "\u2022\u2022\u2022\u2022efgh", expires_at: 4938857803 },
  ],
};

const envPresets = {
  environments: [
    { name: "staging", endpoint: "https://api.staging.example.com", endpoints: { svc: "https://api.staging.example.com" }, default_username: "admin", default_password: "adminpass" },
    { name: "prod", endpoint: "https://api.prod.example.com", endpoints: { svc: "https://api.prod.example.com" }, default_username: "admin", default_password: "adminpass" },
  ],
};

function renderPanel(open = true, onClose = vi.fn()) {
  return render(<AuthPanel open={open} onClose={onClose} />);
}

describe("AuthPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue(profiles);
    envMock.mockResolvedValue(envPresets);
  });

  it("open=false 时不渲染弹层", () => {
    renderPanel(false);
    expect(screen.queryByTestId("auth-panel")).not.toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalled();
  });

  it("open=true 加载 profiles + environments", async () => {
    renderPanel();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(1);
      expect(envMock).toHaveBeenCalledTimes(1);
    });
  });

  it("登录表单默认填充第一个环境的账号密码", async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByTestId("login-username")).toHaveValue("admin");
      expect(screen.getByTestId("login-password")).toHaveValue("adminpass");
    });
  });

  it("点击登录按钮调 loginAuth 并刷新列表", async () => {
    loginMock.mockResolvedValue({ profile: "staging-admin", expires_at: 4939556089 });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId("login-button")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("login-username"), { target: { value: "operator" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "op_pass" } });
    fireEvent.click(screen.getByTestId("login-button"));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        username: "operator", password: "op_pass", endpoint: "https://api.staging.example.com",
        endpoints: { svc: "https://api.staging.example.com" },
      });
    });
    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it("环境按钮可切换，切换后更新账号密码默认值", async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByText("prod")).toBeInTheDocument());
    fireEvent.click(screen.getByText("prod"));
    await waitFor(() => {
      expect(screen.getByTestId("login-username")).toHaveValue("admin");
    });
  });

  it("无预设时显示手动输入端点框", async () => {
    envMock.mockResolvedValue({ environments: [] });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByTestId("manual-endpoint")).toBeInTheDocument();
    });
  });

  it("无预设时登录使用手动输入的端点", async () => {
    envMock.mockResolvedValue({ environments: [] });
    loginMock.mockResolvedValue({ profile: "custom", expires_at: 4939556089 });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId("manual-endpoint")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("manual-endpoint"), { target: { value: "https://custom.example.com" } });
    fireEvent.change(screen.getByTestId("login-username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "pass" } });
    fireEvent.click(screen.getByTestId("login-button"));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        username: "admin", password: "pass", endpoint: "https://custom.example.com", endpoints: undefined,
      });
    });
  });

  it("切换 profile 调 switchProfile 并刷新列表", async () => {
    switchMock.mockResolvedValue({ current: "prod-admin" });
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("profile-row")).toHaveLength(2));
    fireEvent.click(screen.getAllByTestId("switch-profile")[0]);
    await waitFor(() => expect(switchMock).toHaveBeenCalledWith("prod-admin"));
    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it("续签先无密码尝试，失败后弹出密码对话框", async () => {
    refreshMock.mockRejectedValueOnce(new Error("400 PASSWORD_REQUIRED"));
    refreshMock.mockResolvedValueOnce({ profile: "staging-admin", expires_at: 4939556089 });
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("refresh-profile")).toHaveLength(2));

    fireEvent.click(screen.getAllByTestId("refresh-profile")[0]);
    await waitFor(() => expect(screen.getByTestId("refresh-password-input")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("refresh-password-input"), { target: { value: "mypassword" } });
    fireEvent.click(screen.getByTestId("refresh-confirm-button"));

    await waitFor(() => {
      expect(refreshMock).toHaveBeenCalledWith("staging-admin", "mypassword");
    });
  });

  it("profile 缺少用户名时显示提示信息", async () => {
    refreshMock.mockRejectedValue(new Error("400 PROFILE_MISSING_USERNAME"));
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("refresh-profile")).toHaveLength(2));

    fireEvent.click(screen.getAllByTestId("refresh-profile")[0]);
    await waitFor(() => {
      expect(screen.getByTestId("auth-error")).toHaveTextContent("请重新登录");
    });
  });

  it("删除调 deleteAuth", async () => {
    window.confirm = vi.fn().mockReturnValue(true);
    deleteMock.mockResolvedValue({ deleted: "prod-admin" });
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("delete-profile")).toHaveLength(2));
    fireEvent.click(screen.getAllByTestId("delete-profile")[1]);
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("prod-admin"));
  });

  it("已过期的 profile 显示 [已过期]", async () => {
    const expired: ProfileList = {
      current: { name: "old", endpoint: "https://old.com", token_masked: "\u2022\u2022\u2022\u20220000", expires_at: 1000000000 },
      profiles: [{ name: "old", endpoint: "https://old.com", token_masked: "\u2022\u2022\u2022\u20220000", expires_at: 1000000000 }],
    };
    getMock.mockResolvedValue(expired);
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText("[已过期]")).toBeInTheDocument();
    });
  });

  it("无 profile 时显示空态提示", async () => {
    getMock.mockResolvedValue({ current: null, profiles: [] });
    renderPanel();
    await waitFor(() => expect(screen.getByText("未配置环境，请通过上方表单登录")).toBeInTheDocument());
  });

  it("Esc 关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("✕ 按钮关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("auth-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("点击遮罩关闭，点击面板内部不关闭", async () => {
    const onClose = vi.fn();
    renderPanel(true, onClose);
    await waitFor(() => expect(screen.getByTestId("auth-panel")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("auth-panel"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("auth-overlay"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
