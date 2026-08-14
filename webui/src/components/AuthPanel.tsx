import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { getProfiles, switchProfile } from "../api/client";
import type { ProfileList } from "../api/client";
import {
  brand,
  neutral,
  space,
  radius,
  fontSize,
  fontFamily,
  shadow,
} from "../styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

export interface AuthPanelProps {
  /** 受控开关：true 显示弹层 */
  open: boolean;
  onClose: () => void;
}

/** 认证弹层：当前 profile + profile 列表（token 一律显示后端掩码），支持切换。 */
export default function AuthPanel({ open, onClose }: AuthPanelProps) {
  const [data, setData] = useState<ProfileList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [switching, setSwitching] = useState<string | null>(null);

  // 打开时加载 profiles
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    getProfiles()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
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

  const handleSwitch = (name: string) => {
    setSwitching(name);
    setError(null);
    switchProfile(name)
      .then(() => getProfiles())
      .then((res) => setData(res))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSwitching(null));
  };

  return (
    <div
      data-testid="auth-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(15,23,42,.4)",
        ...baseFont,
      }}
    >
      <div
        data-testid="auth-panel"
        style={{
          position: "absolute",
          width: 420,
          maxWidth: "calc(100vw - 48px)",
          maxHeight: "calc(100vh - 96px)",
          overflowY: "auto",
          borderRadius: radius.lg,
          border: `1px solid ${neutral[200]}`,
          backgroundColor: "#FFFFFF",
          boxShadow: shadow.lg,
        }}
      >
        {/* 标题 + ✕ */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: `${space.lg}px ${space.xl}px`,
            borderBottom: `1px solid ${neutral[200]}`,
          }}
        >
          <span style={{ fontSize: fontSize.lg, fontWeight: 600, color: neutral[900] }}>认证</span>
          <button
            type="button"
            className="cliyard-text-btn"
            data-testid="auth-close"
            aria-label="关闭"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div
            data-testid="auth-error"
            style={{
              margin: `${space.lg}px ${space.xl}px 0`,
              padding: `${space.sm}px ${space.md}px`,
              borderRadius: radius.md,
              backgroundColor: "#FEF2F2",
              border: "1px solid #FECACA",
              color: "#DC2626",
              fontSize: fontSize.sm,
            }}
          >
            {error}
          </div>
        )}

        {/* 当前 profile */}
        <div style={{ padding: `${space.lg}px ${space.xl}px`, borderBottom: `1px solid ${neutral[100]}` }}>
          <div
            style={{
              fontSize: fontSize.xs,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: 0.05,
              color: neutral[400],
              marginBottom: space.sm,
            }}
          >
            当前 profile
          </div>
          {current ? (
            <div data-testid="current-profile" style={{ display: "flex", flexDirection: "column", gap: space.xs }}>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.md, fontWeight: 600, color: neutral[800] }}>
                {current.name}
              </span>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500] }}>
                {current.endpoint}
              </span>
              <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[400] }}>
                token: {current.token_masked}
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
          <div
            style={{
              fontSize: fontSize.xs,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: 0.05,
              color: neutral[400],
              marginBottom: space.sm,
            }}
          >
            profiles
          </div>
          {profiles.length === 0 ? (
            <div
              data-testid="auth-empty"
              style={{
                padding: `${space.xl}px ${space.lg}px`,
                borderRadius: radius.md,
                border: `1px dashed ${neutral[200]}`,
                backgroundColor: neutral[50],
                color: neutral[400],
                fontSize: fontSize.sm,
                textAlign: "center",
              }}
            >
              未配置 profile，请使用 cliyard auth add 添加
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: space.sm }}>
              {profiles.map((p) => {
                const isCurrent = current?.name === p.name;
                return (
                  <div
                    key={p.name}
                    data-testid="profile-row"
                    data-active={isCurrent ? "true" : "false"}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: space.md,
                      padding: `${space.md}px ${space.lg}px`,
                      borderRadius: radius.md,
                      border: `1px solid ${isCurrent ? brand[200] : neutral[200]}`,
                      backgroundColor: isCurrent ? brand[50] : "#FFFFFF",
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.md, fontWeight: 600, color: isCurrent ? brand[600] : neutral[800] }}>
                        {p.name}
                      </span>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500] }}>
                        {p.endpoint}
                      </span>
                      <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[400] }}>
                        {p.token_masked}
                      </span>
                    </div>
                    {isCurrent ? (
                      <span style={{ fontSize: fontSize.xs, color: brand[600], fontWeight: 500, whiteSpace: "nowrap" }}>
                        当前
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="cliyard-outline-btn"
                        data-testid="switch-profile"
                        disabled={switching !== null}
                        onClick={() => handleSwitch(p.name)}
                      >
                        {switching === p.name ? "切换中…" : "切换"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
