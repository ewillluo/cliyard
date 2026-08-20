import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { getProfiles, switchProfile, loginAuth, refreshAuth, deleteAuth, fetchEnvironments } from "../api/client";
import type { ProfileList, AuthProfile, EnvPreset } from "../api/client";
import { brand, neutral, space, radius, fontSize, fontFamily, shadow, statusColors } from "../styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

export interface AuthPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function AuthPanel({ open, onClose }: AuthPanelProps) {
  const [data, setData] = useState<ProfileList | null>(null);
  const [presets, setPresets] = useState<EnvPreset[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 登录表单
  const [selectedPreset, setSelectedPreset] = useState<EnvPreset | null>(null);
  const [manualEndpoint, setManualEndpoint] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  // 列表操作
  const [switching, setSwitching] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [refreshPwDialog, setRefreshPwDialog] = useState<{ profile: string; username: string } | null>(null);
  const [refreshPwValue, setRefreshPwValue] = useState("");

  // 加载数据
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    Promise.all([getProfiles(), fetchEnvironments()])
      .then(([profiles, envRes]) => {
        if (cancelled) return;
        setData(profiles);
        setPresets(envRes.environments);
        if (envRes.environments.length > 0) {
          const first = envRes.environments[0];
          setSelectedPreset(first);
          setUsername(first.default_username ?? "");
          // 只预填用户名，不预填密码（安全）
          setPassword("");
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => { cancelled = true; };
  }, [open]);

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const current = data?.current ?? null;
  const profiles = data?.profiles ?? [];
  const loginEndpoint = selectedPreset?.endpoint ?? manualEndpoint;

  const confirmRefreshWithPw = async () => {
    if (!refreshPwDialog) return;
    setRefreshing(refreshPwDialog.profile);
    setError(null);
    try {
      await refreshAuth(refreshPwDialog.profile, refreshPwValue);
      const res = await getProfiles();
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(null);
      setRefreshPwDialog(null);
      setRefreshPwValue("");
    }
  };

  const handleLogin = () => {
    if (!loginEndpoint) return;
    setLoggingIn(true);
    setError(null);
    loginAuth({ username, password, endpoint: loginEndpoint, endpoints: selectedPreset?.endpoints, env_name: selectedPreset?.name })
      .then(() => getProfiles())
      .then((res) => setData(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoggingIn(false));
  };

  const handleSwitch = (name: string) => {
    setSwitching(name);
    setError(null);
    switchProfile(name)
      .then(() => getProfiles())
      .then((res) => setData(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSwitching(null));
  };

  const handleRefresh = async (name: string) => {
    setRefreshing(name);
    setError(null);
    try {
      await refreshAuth(name);
      const res = await getProfiles();
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("PASSWORD_REQUIRED")) {
        const profile = profiles.find((p) => p.name === name);
        setRefreshPwDialog({ profile: name, username: profile?.auth_username ?? "" });
      } else if (msg.includes("PROFILE_MISSING_USERNAME")) {
        setError(`profile "${name}" 缺少用户名，请重新登录`);
      } else {
        setError(msg);
      }
    } finally {
      setRefreshing(null);
    }
  };

  const handleDelete = (name: string) => {
    if (!window.confirm(`确认删除 ${name}？`)) return;
    setError(null);
    deleteAuth(name)
      .then(() => getProfiles())
      .then((res) => setData(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  };

  const expiryText = (p: AuthProfile): string => {
    if (!p.expires_at) return "未记录";
    const remaining = Number(p.expires_at) * 1000 - Date.now();
    if (remaining <= 0) return "已过期";
    const hours = Math.floor(remaining / 3600000);
    const mins = Math.floor((remaining % 3600000) / 60000);
    return `${hours}h ${mins}m 剩余`;
  };

  const isExpired = (p: AuthProfile): boolean => {
    if (!p.expires_at) return false;
    return Number(p.expires_at) * 1000 <= Date.now();
  };

  return (
    <div
      data-testid="auth-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 100, display: "flex", alignItems: "flex-start",
        justifyContent: "center", paddingTop: 80, backgroundColor: "rgba(15,23,42,.4)", ...baseFont,
      }}
    >
      <div
        data-testid="auth-panel"
        style={{
          width: 520, maxWidth: "calc(100vw - 48px)", maxHeight: "calc(100vh - 96px)",
          overflowY: "auto", borderRadius: radius.lg, border: `1px solid ${neutral[200]}`,
          backgroundColor: "#FFFFFF", boxShadow: shadow.lg,
        }}
      >
        {/* ═══ 标题行 ═══ */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: `${space.lg}px ${space.xl}px`, borderBottom: `1px solid ${neutral[200]}` }}>
          <span style={{ fontSize: fontSize.lg, fontWeight: 600, color: neutral[900] }}>登录认证</span>
          <button type="button" className="cliyard-text-btn" data-testid="auth-close" aria-label="关闭" onClick={onClose}>
            <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* ═══ 错误提示 ═══ */}
        {error && (
          <div data-testid="auth-error" style={{ margin: `${space.lg}px ${space.xl}px 0`, padding: `${space.sm}px ${space.md}px`,
            borderRadius: radius.md, backgroundColor: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626", fontSize: fontSize.sm }}>
            {error}
          </div>
        )}

        {/* ════════════════════════════════ */}
        {/* 上半部：登录表单                    */}
        {/* ════════════════════════════════ */}
        <div style={{ padding: `${space.lg}px ${space.xl}px`, borderBottom: `1px solid ${neutral[100]}` }}>
          <div style={{ fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05,
            color: neutral[400], marginBottom: space.md }}>
            登录
          </div>

          {/* 环境预设选择 */}
          {presets.length > 0 && (
            <div style={{ display: "flex", gap: space.sm, marginBottom: space.sm, flexWrap: "wrap" }}>
              {presets.map((env) => (
                <button key={env.name} type="button"
                  onClick={() => { setSelectedPreset(env); setUsername(env.default_username ?? ""); setPassword(""); }}
                  style={{
                    padding: `${space.xs}px ${space.md}px`, borderRadius: radius.md,
                    border: `1px solid ${selectedPreset?.name === env.name ? brand[200] : neutral[200]}`,
                    backgroundColor: selectedPreset?.name === env.name ? brand[50] : "#FFFFFF",
                    color: selectedPreset?.name === env.name ? brand[700] : neutral[600],
                    fontSize: fontSize.sm, fontWeight: 500, cursor: "pointer",
                  }}>
                  {env.name}
                </button>
              ))}
            </div>
          )}

          {/* 端点 */}
          {presets.length > 0 ? (
            <div style={{ fontSize: fontSize.xs, color: neutral[400], marginBottom: space.sm, fontFamily: fontFamily.mono }}>
              {loginEndpoint}
            </div>
          ) : (
            <input data-testid="manual-endpoint" type="text" placeholder="输入端点 URL，如 https://api.example.com"
              value={manualEndpoint} onChange={(e) => setManualEndpoint(e.target.value)}
              style={{ width: "100%", padding: `${space.sm}px ${space.md}px`, border: `1px solid ${neutral[300]}`,
                borderRadius: radius.md, fontSize: fontSize.sm, fontFamily: fontFamily.mono, marginBottom: space.sm, boxSizing: "border-box" }} />
          )}

          {/* 账号密码 */}
          <div style={{ display: "flex", gap: space.sm, marginBottom: space.md }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: fontSize.xs, color: neutral[500], marginBottom: 2 }}>账号</div>
              <input data-testid="login-username" type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                style={{ width: "100%", padding: `${space.sm}px ${space.md}px`, border: `1px solid ${neutral[300]}`,
                  borderRadius: radius.md, fontSize: fontSize.sm, fontFamily: fontFamily.mono, boxSizing: "border-box" }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: fontSize.xs, color: neutral[500], marginBottom: 2 }}>密码</div>
              <input data-testid="login-password" type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleLogin(); }}
                style={{ width: "100%", padding: `${space.sm}px ${space.md}px`, border: `1px solid ${neutral[300]}`,
                  borderRadius: radius.md, fontSize: fontSize.sm, fontFamily: fontFamily.mono, boxSizing: "border-box" }} />
            </div>
          </div>

          {/* 登录按钮 */}
          <button type="button" data-testid="login-button" disabled={loggingIn || !loginEndpoint || !username || !password}
            onClick={handleLogin}
            style={{ width: "100%", padding: `${space.sm + 2}px`, borderRadius: radius.md, border: "none",
              backgroundColor: brand[500], color: "#FFFFFF", fontSize: fontSize.md, fontWeight: 600, cursor: "pointer",
              opacity: loggingIn || !loginEndpoint || !username || !password ? 0.6 : 1 }}>
            {loggingIn ? "登录中..." : "登录并设为当前"}
          </button>
        </div>

        {/* ════════════════════════════════ */}
        {/* 下半部：当前 profile + 列表       */}
        {/* ════════════════════════════════ */}

        {/* 当前 profile */}
        <div style={{ padding: `${space.lg}px ${space.xl}px`, borderBottom: `1px solid ${neutral[100]}` }}>
          <div style={{ fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05,
            color: neutral[400], marginBottom: space.sm }}>
            当前环境
          </div>
          {current ? (
            <div data-testid="current-profile" style={{ display: "flex", flexDirection: "column", gap: space.xs }}>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.md, fontWeight: 600, color: neutral[800] }}>
                {current.name}
              </span>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500] }}>
                {current.endpoint}
              </span>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: isExpired(current) ? statusColors.error.color : neutral[400] }}>
                token: {current.token_masked} · {expiryText(current)}
              </span>
            </div>
          ) : (
            <div data-testid="current-profile" style={{ fontSize: fontSize.sm, color: neutral[400] }}>
              未选择
            </div>
          )}
        </div>

        {/* profile 列表 */}
        <div style={{ padding: `${space.lg}px ${space.xl}px` }}>
          <div style={{ fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05,
            color: neutral[400], marginBottom: space.sm }}>
            已保存环境
          </div>
          {profiles.length === 0 ? (
            <div data-testid="auth-empty" style={{ padding: `${space.xl}px ${space.lg}px`, borderRadius: radius.md,
              border: `1px dashed ${neutral[200]}`, backgroundColor: neutral[50], color: neutral[400],
              fontSize: fontSize.sm, textAlign: "center" }}>
              未配置环境，请通过上方表单登录
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: space.sm }}>
              {profiles.map((p) => {
                const isCurrent = current?.name === p.name;
                const expired = isExpired(p);
                return (
                  <div key={p.name} data-testid="profile-row" data-active={isCurrent ? "true" : "false"}
                    style={{ display: "flex", alignItems: "center", gap: space.md, padding: `${space.md}px ${space.lg}px`,
                      borderRadius: radius.md, border: `1px solid ${expired ? statusColors.error.border : isCurrent ? brand[200] : neutral[200]}`,
                      backgroundColor: expired ? "#FEF2F2" : isCurrent ? brand[50] : "#FFFFFF" }}>
                    <div style={{ minWidth: 0, flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.md, fontWeight: 600, color: isCurrent ? brand[600] : neutral[800] }}>
                        {p.name}
                        {expired && <span style={{ color: statusColors.error.color, fontSize: fontSize.xs, marginLeft: space.sm }}>[已过期]</span>}
                      </span>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500] }}>
                        {p.endpoint}
                      </span>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[400] }}>
                        {p.token_masked} · {expiryText(p)}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: space.xs, flexShrink: 0 }}>
                      {isCurrent ? (
                        <span style={{ fontSize: fontSize.xs, color: brand[600], fontWeight: 500, whiteSpace: "nowrap", paddingRight: space.sm }}>
                          当前
                        </span>
                      ) : (
                        <button type="button" className="cliyard-outline-btn" data-testid="switch-profile"
                          disabled={switching !== null} onClick={() => handleSwitch(p.name)}>
                          {switching === p.name ? "..." : "切换"}
                        </button>
                      )}
                      <button type="button" className="cliyard-outline-btn" data-testid="refresh-profile"
                        disabled={refreshing !== null} onClick={() => handleRefresh(p.name)}>
                        {refreshing === p.name ? "..." : "续签"}
                      </button>
                      <button type="button" className="cliyard-outline-btn" data-testid="delete-profile"
                        onClick={() => handleDelete(p.name)}
                        style={{ color: statusColors.error.color, borderColor: statusColors.error.border }}>
                        删除
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ═══ 续签密码弹窗 ═══ */}
      {refreshPwDialog && (
        <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center",
          justifyContent: "center", backgroundColor: "rgba(0,0,0,.3)", ...baseFont }}
          onClick={() => setRefreshPwDialog(null)}>
          <div style={{ background: "#fff", borderRadius: radius.lg, padding: `${space.xl}px`, width: 320, boxShadow: shadow.lg }}
            onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: fontSize.md, fontWeight: 600, marginBottom: space.sm }}>
              续签 {refreshPwDialog.profile}
            </div>
            <div style={{ fontSize: fontSize.xs, color: neutral[500], marginBottom: space.md }}>
              账号：{refreshPwDialog.username}
            </div>
            <input data-testid="refresh-password-input" type="password" autoComplete="off" placeholder="输入密码"
              value={refreshPwValue} onChange={(e) => setRefreshPwValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirmRefreshWithPw(); }}
              style={{ width: "100%", padding: `${space.sm}px ${space.md}px`, border: `1px solid ${neutral[300]}`,
                borderRadius: radius.md, fontSize: fontSize.sm, fontFamily: fontFamily.mono, marginBottom: space.md, boxSizing: "border-box" }} />
            <div style={{ display: "flex", gap: space.sm, justifyContent: "flex-end" }}>
              <button type="button" className="cliyard-outline-btn"
                onClick={() => { setRefreshPwDialog(null); setRefreshPwValue(""); }}>
                取消
              </button>
              <button type="button" data-testid="refresh-confirm-button" disabled={!refreshPwValue}
                onClick={confirmRefreshWithPw}
                style={{ padding: `${space.sm}px ${space.lg}px`, borderRadius: radius.md, border: "none",
                  backgroundColor: brand[500], color: "#FFFFFF", fontSize: fontSize.sm, fontWeight: 600, cursor: "pointer",
                  opacity: refreshPwValue ? 1 : 0.6 }}>
                确认续签
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
