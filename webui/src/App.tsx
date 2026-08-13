import type { CSSProperties } from "react";
import TopBar from "./components/TopBar";
import { neutral, space, radius, fontSize, fontFamily, shadow } from "./styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

/** 卡片外壳：白底 + 1px 边框 + 轻阴影 + 大圆角（对齐原型 cardBase） */
const cardBase: CSSProperties = {
  backgroundColor: "#FFFFFF",
  border: `1px solid ${neutral[200]}`,
  borderRadius: radius.lg,
  boxShadow: shadow.sm,
};

/** 三栏空骨架占位标签 */
function PanelPlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: space.sm }}>
      <div style={{ fontSize: fontSize.md, fontWeight: 600, color: neutral[700], ...baseFont }}>{title}</div>
      <div style={{ fontSize: fontSize.xs, color: neutral[400], ...baseFont }}>{note}</div>
    </div>
  );
}

/**
 * 应用外壳：顶栏 + 三栏空骨架
 * 左 240px（命令树）/ 中 320px（命令表单）/ 右 flex-1（执行步骤/历史）
 * 业务组件（CommandTree / CommandForm / StepsPanel）在 T9/T10/T11 实现
 */
export default function App() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100%",
        backgroundColor: neutral[50],
        ...baseFont,
      }}
    >
      <TopBar />

      {/* 内容区：三栏 */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", gap: space.lg, padding: space.xl }}>
        {/* ① 命令树（T9） */}
        <aside data-testid="command-tree" style={{ width: 240, flexShrink: 0, ...cardBase, padding: space.lg }}>
          <PanelPlaceholder title="命令树" note="T9 · YAML spec 命令列表" />
        </aside>

        {/* ② 命令表单（T10） */}
        <section data-testid="command-form" style={{ width: 320, flexShrink: 0, ...cardBase, padding: space.lg }}>
          <PanelPlaceholder title="命令表单" note="T10 · rjsf 按 JSON Schema 渲染" />
        </section>

        {/* ③ 执行步骤 / 历史（T11） */}
        <section data-testid="right-panel" style={{ minWidth: 0, flex: 1, ...cardBase, padding: space.lg }}>
          <PanelPlaceholder title="执行步骤 / 历史记录" note="T11 · 执行时间线与历史表格" />
        </section>
      </div>
    </div>
  );
}
