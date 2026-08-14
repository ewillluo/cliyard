import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import type { CSSProperties, Ref } from "react";
import { clearExecutions, listExecutions, replayExecution } from "../api/client";
import type { HistoryItem } from "../api/client";
import {
  brand,
  neutral,
  space,
  radius,
  fontSize,
  fontFamily,
  statusColors,
} from "../styles/tokens";

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

/** 每页条数（对齐后端 limit 默认值） */
const PAGE_SIZE = 20;

export interface HistoryPanelHandle {
  /** 重新加载当前页 */
  reload: () => void;
  /** 清空全部历史并回到第 1 页刷新 */
  clear: () => Promise<void>;
}

export interface HistoryPanelProps {
  /** 重放成功后回调新 execution_id（父级切回「执行步骤」tab 并订阅 SSE） */
  onReExecute: (executionId: string) => void;
}

/** ISO 时间 → "HH:MM:SS"（对齐原型历史表开始时间列） */
function timeToDisplay(iso: string): string {
  return iso.length >= 19 ? iso.slice(11, 19) : iso;
}

/** duration_ms → "129ms" / "1.2s"，空值显示 "—" */
function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** "repos.list" → 资源名品牌蓝 + 方法深色；flow 前加品牌蓝 "flow" 前缀（对齐原型 CommandCell） */
function CommandCell({ kind, target }: { kind: string; target: string }) {
  const sep = Math.max(target.indexOf("."), target.indexOf(" "));
  const hasSep = sep > 0;
  return (
    <span style={{ fontFamily: fontFamily.mono, fontWeight: 500 }}>
      {kind === "flow" && <span style={{ color: brand[600] }}>flow </span>}
      {hasSep ? (
        <>
          <span style={{ color: brand[600] }}>{target.slice(0, sep)}</span>
          <span style={{ color: neutral[800] }}>{target.slice(sep)}</span>
        </>
      ) : (
        <span style={{ color: neutral[800] }}>{target}</span>
      )}
    </span>
  );
}

/** 历史状态 pill：done→成功绿 / error→失败红 / running→品牌蓝（浅底 + 1px 彩边） */
function StatusPill({ status }: { status: string }) {
  const t =
    status === "error"
      ? statusColors.error
      : status === "running"
        ? statusColors.running
        : statusColors.success;
  const label = status === "error" ? "失败" : status === "running" ? "执行中" : "成功";
  return (
    <span
      data-testid="history-status"
      data-status={status}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: space.xs,
        padding: `${space.xs - 1}px ${space.sm + 2}px`,
        borderRadius: radius.pill,
        backgroundColor: t.bg,
        border: `1px solid ${t.border}`,
        color: t.color,
        fontSize: fontSize.xs,
        fontWeight: 500,
        lineHeight: 1.4,
        whiteSpace: "nowrap",
        ...baseFont,
      }}
    >
      <span
        aria-hidden
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: t.color,
          flexShrink: 0,
        }}
      />
      {label}
    </span>
  );
}

/** 空态占位 */
function EmptyState({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 160,
        margin: `${space.lg}px 0`,
        borderRadius: radius.md,
        border: `1px dashed ${neutral[200]}`,
        backgroundColor: neutral[50],
        color: neutral[400],
        fontSize: fontSize.sm,
        ...baseFont,
      }}
    >
      {text}
    </div>
  );
}

const thStyle: CSSProperties = {
  padding: `${space.sm + 2}px ${space.lg}px`,
  fontSize: fontSize.xs,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: 0.05,
  color: neutral[400],
};

const tdMono: CSSProperties = {
  padding: `${space.md}px ${space.lg}px`,
  fontFamily: fontFamily.mono,
  color: neutral[500],
  whiteSpace: "nowrap",
};

/**
 * 执行历史表格：时间倒序 + 分页（每页 20）+ 重放。
 * 挂载即加载；通过 ref 暴露 reload/clear 供 StepsPanel tab bar 按钮调用。
 */
function HistoryPanelInner(props: HistoryPanelProps, ref: Ref<HistoryPanelHandle>) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [replayingId, setReplayingId] = useState<string | null>(null);

  const load = useCallback((pageNum: number) => {
    setLoading(true);
    setError(null);
    listExecutions(PAGE_SIZE, (pageNum - 1) * PAGE_SIZE)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(page);
  }, [page, reloadKey, load]);

  useImperativeHandle(ref, () => ({
    reload: () => setReloadKey((k) => k + 1),
    clear: async () => {
      await clearExecutions();
      setItems([]);
      setTotal(0);
      setPage(1);
      setReloadKey((k) => k + 1);
    },
  }));

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleReplay = (id: string) => {
    setReplayingId(id);
    replayExecution(id)
      .then(({ execution_id }) => props.onReExecute(execution_id))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setReplayingId(null));
  };

  return (
    <div style={{ padding: space.lg }}>
      {error && (
        <div
          data-testid="history-error"
          style={{
            marginBottom: space.md,
            padding: `${space.sm}px ${space.md}px`,
            borderRadius: radius.md,
            backgroundColor: statusColors.error.bg,
            border: `1px solid ${statusColors.error.border}`,
            color: statusColors.error.color,
            fontSize: fontSize.sm,
            ...baseFont,
          }}
        >
          {error}
        </div>
      )}

      {items.length === 0 ? (
        !loading && <EmptyState text="暂无执行历史" />
      ) : (
        <div style={{ overflow: "hidden", borderRadius: radius.md, border: `1px solid ${neutral[200]}` }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: fontSize.sm, ...baseFont }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${neutral[200]}`, backgroundColor: neutral[50] }}>
                <th style={thStyle}>开始时间</th>
                <th style={thStyle}>命令</th>
                <th style={thStyle}>状态</th>
                <th style={thStyle}>耗时</th>
                <th style={thStyle}>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr
                  key={it.id}
                  data-testid="history-row"
                  className="cliyard-row"
                  style={{ borderBottom: `1px solid ${neutral[100]}` }}
                >
                  <td style={tdMono}>{timeToDisplay(it.created_at)}</td>
                  <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                    <CommandCell kind={it.kind} target={it.target} />
                  </td>
                  <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                    <StatusPill status={it.status} />
                  </td>
                  <td style={tdMono}>{formatDuration(it.duration_ms)}</td>
                  <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                    <button
                      type="button"
                      className="cliyard-text-btn"
                      data-testid="replay-button"
                      disabled={replayingId === it.id}
                      onClick={() => handleReplay(it.id)}
                    >
                      {replayingId === it.id ? "重放中…" : "重放"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div
        style={{
          marginTop: space.md,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: fontSize.xs,
          color: neutral[400],
          ...baseFont,
        }}
      >
        <span data-testid="history-count" style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs }}>
          共 {total} 条 · 第 {page} / {pageCount} 页
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: space.sm }}>
          <button
            type="button"
            className="cliyard-text-btn"
            data-testid="history-prev"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <button
            type="button"
            className="cliyard-text-btn"
            data-testid="history-next"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}

export default forwardRef<HistoryPanelHandle, HistoryPanelProps>(HistoryPanelInner);
