import type { CSSProperties } from "react";
import {
  brand,
  neutral,
  space,
  radius,
  fontSize,
  fontFamily,
  shadow,
  statusColors,
} from "../styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

/**
 * 顶栏：浅色白底 height 60（对齐原型 command-panel 顶栏）
 * 左：品牌 C 标 + 标题 + spec 副标题；右：运行状态 pill + 「认证」按钮
 */
export default function TopBar({ onAuthClick }: { onAuthClick?: () => void }) {
  return (
    <header
      data-testid="topbar"
      style={{
        height: 60,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: space.xl,
        padding: `0 ${space.xl}px`,
        backgroundColor: "#FFFFFF",
        borderBottom: `1px solid ${neutral[200]}`,
        ...baseFont,
      }}
    >
      {/* 左：品牌 C 标 + 标题 + spec 副标题 */}
      <div style={{ display: "flex", alignItems: "center", gap: space.md, minWidth: 0 }}>
        <span
          aria-hidden
          style={{
            width: 34,
            height: 34,
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: radius.md,
            backgroundColor: brand[500],
            color: "#FFFFFF",
            fontWeight: 700,
            fontSize: fontSize.lg,
            boxShadow: shadow.brand,
          }}
        >
          C
        </span>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: fontSize.xl,
              fontWeight: 600,
              color: neutral[900],
              lineHeight: 1.3,
              whiteSpace: "nowrap",
            }}
          >
            cliyard-web
          </div>
          <div style={{ fontSize: fontSize.xs, color: neutral[400], marginTop: 1, whiteSpace: "nowrap" }}>
            spec: ./examples/demo
          </div>
        </div>
      </div>

      {/* 右：运行状态 pill + 「认证」按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: space.sm }}>
        <span
          data-testid="status-pill"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: space.xs,
            padding: `${space.xs - 1}px ${space.sm + 2}px`,
            borderRadius: radius.pill,
            backgroundColor: statusColors.success.bg,
            border: `1px solid ${statusColors.success.border}`,
            color: statusColors.success.color,
            fontSize: fontSize.sm,
            fontWeight: 500,
            whiteSpace: "nowrap",
            ...baseFont,
          }}
        >
          <span
            aria-hidden
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              backgroundColor: statusColors.success.color,
              flexShrink: 0,
            }}
          />
          运行中 · :8080
        </span>
        <button type="button" className="cliyard-text-btn" data-testid="auth-button" onClick={onAuthClick}>
          登录认证
        </button>
      </div>
    </header>
  );
}
