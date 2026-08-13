import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import TopBar from "./components/TopBar";
import CommandTree from "./components/CommandTree";
import type { Selection } from "./components/CommandTree";
import { fetchSpec } from "./api/client";
import type { SpecData } from "./api/client";
import { neutral, space, radius, fontSize, fontFamily, shadow, statusColors } from "./styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

/** 卡片外壳：白底 + 1px 边框 + 轻阴影 + 大圆角（对齐原型 cardBase） */
const cardBase: CSSProperties = {
  backgroundColor: "#FFFFFF",
  border: `1px solid ${neutral[200]}`,
  borderRadius: radius.lg,
  boxShadow: shadow.sm,
};

/** 三栏占位标签（中/右面板 T10/T11 实现前占位） */
function PanelPlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: space.sm }}>
      <div style={{ fontSize: fontSize.md, fontWeight: 600, color: neutral[700], ...baseFont }}>{title}</div>
      <div style={{ fontSize: fontSize.xs, color: neutral[400], ...baseFont }}>{note}</div>
    </div>
  );
}

/**
 * 应用外壳：顶栏 + 三栏
 * 左 240px（命令树，T9：fetchSpec + CommandTree）/ 中 320px（命令表单 T10）/ 右 flex-1（执行步骤/历史 T11）
 */
export default function App() {
  const [spec, setSpec] = useState<SpecData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Selection | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSpec()
      .then((data) => {
        if (!cancelled) setSpec(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
        <aside
          data-testid="command-tree"
          style={{ width: 240, flexShrink: 0, ...cardBase, padding: space.lg, overflowY: "auto" }}
        >
          {loadError ? (
            <div style={{ fontSize: fontSize.xs, color: statusColors.error.color, ...baseFont }}>
              加载失败：{loadError}
            </div>
          ) : spec ? (
            <CommandTree spec={spec} selected={selected} onSelect={setSelected} />
          ) : (
            <div style={{ fontSize: fontSize.xs, color: neutral[400], ...baseFont }}>加载中…</div>
          )}
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
