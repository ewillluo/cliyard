import { useState } from "react";
import type { CSSProperties } from "react";
import type { PrototypeDef, PrototypeRenderProps } from "@md-docs/prototypes/types";
import { IconSearch, IconRefresh } from "@md-docs/prototypes/_shared/ui";
import {
  brand,
  neutral,
  space,
  radius,
  fontSize,
  fontFamily,
  shadow,
  statusColors,
  type StatusTheme,
} from "../_shared/styles";

/**
 * 主界面原型：命令树 + 命令表单 + 执行步骤/历史（三栏单页）
 * =====================================================
 * 视觉风格对齐 aiagents 原型（inline style + 设计 token，见 _shared/styles.ts）：
 * ① 左侧命令树（资源分组 + labels badge，选中项 3px 品牌蓝指示条 + 浅蓝底）
 * ② 中间 JSON Schema 自动渲染表单
 * ③ 右侧 tab：执行步骤流 / 历史记录（独立 history 页面已并入此 tab）
 */

/* ---------- 数据模型 ---------- */

type TreeItem = {
  name: string;
  labels: string[];
  desc: string;
  tags?: string[];
};

const tree: { group: string; desc: string; items: TreeItem[] }[] = [
  {
    group: "repos",
    desc: "仓库管理",
    items: [
      { name: "list", labels: ["已调试", "v2"], desc: "列出仓库" },
      { name: "create", labels: ["已调试"], desc: "创建仓库" },
      { name: "delete", labels: [], desc: "删除仓库" },
    ],
  },
  {
    group: "users",
    desc: "用户管理",
    items: [
      { name: "list", labels: [], desc: "列出用户" },
      { name: "reset-pwd", labels: [], desc: "重置密码", tags: ["danger"] },
    ],
  },
];

type Step = {
  title: string;
  time: string;
  status: "done" | "running" | "error" | "pending";
  body: string[];
  mono?: boolean;
  /** flow 编排步骤：对应 _flow_*.yaml 中 steps[].use（如 user.list） */
  use?: string;
};

const steps: Step[] = [
  {
    title: "参数校验",
    time: "14:23:01.204",
    status: "done",
    body: [
      "已绑定 5 个参数：",
      "  name = cliyard / format = json / page_size = 20 / verbose = false",
      "  token = ••••••••（来自 saved profile: dev）",
    ],
  },
  {
    title: "认证准备",
    time: "14:23:01.205",
    status: "done",
    body: ["使用 profile「dev」：Bearer token，有效期至 2026-08-20 14:23"],
  },
  {
    title: "发送请求",
    time: "14:23:01.206",
    status: "done",
    mono: true,
    body: [
      "GET https://api.example.com/api/v1/repos?page_size=20",
      "Authorization: Bearer ••••••••",
      "Accept: application/json",
    ],
  },
  {
    title: "等待响应",
    time: "14:23:01.332",
    status: "done",
    body: ["HTTP 200 · 126ms"],
  },
  {
    title: "格式化结果",
    time: "14:23:01.333",
    status: "done",
    mono: true,
    body: [
      "{",
      '  "code": 0,',
      '  "msg": "ok",',
      '  "data": [ { "id": 1, "name": "cliyard" } ]',
      "}",
    ],
  },
  {
    title: "完成",
    time: "…",
    status: "running",
    body: ["执行中，等待退出状态…"],
  },
];

type HistoryRow = {
  time: string;
  command: string;
  status: "success" | "error";
  duration: string;
};

const historyRows: HistoryRow[] = [
  { time: "14:23:01", command: "repos list", status: "success", duration: "129ms" },
  { time: "14:20:44", command: "repos create", status: "success", duration: "1.2s" },
  { time: "14:18:12", command: "users reset-pwd", status: "error", duration: "340ms" },
  { time: "14:10:03", command: "repos delete", status: "success", duration: "86ms" },
  { time: "13:58:29", command: "users list", status: "success", duration: "95ms" },
];

/* ---------- flow 数据（对应 examples/demo/flows/_flows.yaml） ---------- */

type FlowParam = {
  name: string;
  type: string;
  required?: boolean;
  description?: string;
};

type Flow = {
  name: string;
  description: string;
  command: string;
  params?: FlowParam[];
  /** 编排步骤数（不含参数校验/完成前后置） */
  stepCount: number;
};

const flows: Flow[] = [
  {
    name: "add_user",
    description: "新增用户（查→判→创→验）",
    command: "add-user",
    params: [
      { name: "name", type: "string", required: true, description: "用户名" },
      { name: "phone", type: "string", description: "手机号" },
    ],
    stepCount: 4,
  },
  { name: "retry_demo", description: "演示重试机制", command: "retry-demo", stepCount: 3 },
  { name: "plugin_demo", description: "演示插件步骤", command: "plugin-demo", stepCount: 3 },
  { name: "hook_demo", description: "演示生命周期钩子", command: "hook-demo", stepCount: 4 },
];

/** add_user 流程编排模拟步骤（对应 _flow_add_user.yaml：查→判→创→验） */
const flowSteps: Step[] = [
  {
    title: "参数校验",
    time: "14:30:01.102",
    status: "done",
    body: ["已绑定 2 个参数：", "  name = alice / phone = 13800138000"],
  },
  {
    title: "步骤 1/4 · check_user",
    time: "14:30:01.110",
    status: "done",
    use: "user.list",
    body: ["GET https://api.example.com/api/v1/users?name=alice", "→ 0 条记录 · found_users = []"],
  },
  {
    title: "步骤 2/4 · decision",
    time: "14:30:01.112",
    status: "done",
    use: "分支判断",
    body: ["found_users 为空 → 走「创建用户」分支", "{{ step.check_user.found_users | length > 0 }} = false"],
  },
  {
    title: "步骤 3/4 · create_user",
    time: "14:30:01.204",
    status: "running",
    use: "user.create",
    body: ["POST https://api.example.com/api/v1/users", "name = alice / phone = 13800138000"],
  },
  {
    title: "步骤 4/4 · verify_user",
    time: "…",
    status: "pending",
    use: "user.list",
    body: ["等待 create_user 完成，验证用户已创建…"],
  },
  {
    title: "完成",
    time: "…",
    status: "pending",
    body: ["流程执行中，等待退出状态…"],
  },
];

/* ---------- scoped 样式与动画（颜色/间距全部取自 token，前缀 cliyard- 避免污染） ---------- */

const cliCss = `
  @keyframes cliyard-breathe { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* 文本按钮：hover 变浅灰底 */
  .cliyard-text-btn {
    border: none; background: transparent; cursor: pointer;
    border-radius: ${radius.md}px;
    padding: ${space.sm - 2}px ${space.sm + 2}px;
    font-size: ${fontSize.sm}px; color: ${neutral[500]};
    font-family: ${fontFamily.body};
    transition: background-color .15s ease, color .15s ease;
  }
  .cliyard-text-btn:hover { background-color: ${neutral[100]}; color: ${neutral[900]}; }

  /* outline 按钮：白底 + 1px 边框 */
  .cliyard-outline-btn {
    display: inline-flex; align-items: center; gap: ${space.xs}px;
    border: 1px solid ${neutral[200]}; background-color: #FFFFFF; cursor: pointer;
    border-radius: ${radius.md}px;
    padding: ${space.sm - 2}px ${space.md}px;
    font-size: ${fontSize.sm}px; color: ${neutral[600]};
    font-family: ${fontFamily.body};
    box-shadow: ${shadow.sm};
    transition: border-color .15s ease, background-color .15s ease, color .15s ease;
  }
  .cliyard-outline-btn:hover { border-color: ${neutral[300]}; background-color: ${neutral[50]}; color: ${neutral[900]}; }

  /* 主按钮：品牌蓝纯色 + 白字 + 光晕（pill） */
  .cliyard-pill-btn {
    display: inline-flex; align-items: center; justify-content: center; gap: ${space.xs}px;
    border: none; border-radius: ${radius.pill}px;
    background-color: ${brand[600]}; color: #FFFFFF;
    font-size: ${fontSize.md}px; font-weight: 500;
    font-family: ${fontFamily.body};
    cursor: pointer; box-shadow: ${shadow.brand};
    transition: background-color .15s ease, box-shadow .15s ease;
  }
  .cliyard-pill-btn:hover { background-color: ${brand[700]}; box-shadow: none; }

  /* 命令树项：hover 浅灰，选中浅蓝底（选中指示条由 inline 渲染） */
  .cliyard-tree-item {
    position: relative; display: flex; align-items: center; gap: ${space.sm}px;
    width: 100%; padding: ${space.sm - 2}px ${space.md}px ${space.sm - 2}px ${space.md + 4}px;
    border: none; border-radius: ${radius.md}px; cursor: pointer; text-align: left;
    background-color: transparent; color: ${neutral[600]};
    font-size: ${fontSize.sm}px; font-family: ${fontFamily.mono};
    transition: background-color .15s ease, color .15s ease;
  }
  .cliyard-tree-item:hover { background-color: ${neutral[100]}; color: ${neutral[900]}; }
  .cliyard-tree-item[data-active="true"] { background-color: ${brand[50]}; color: ${brand[600]}; font-weight: 500; }
  .cliyard-tree-item[data-active="true"]:hover { background-color: ${brand[50]}; color: ${brand[600]}; }

  /* flow 列表项：两行布局（名称行 + 描述行），选中态同命令树 */
  .cliyard-flow-item {
    position: relative; display: flex; flex-direction: column; gap: 2px;
    width: 100%; padding: ${space.sm}px ${space.md}px ${space.sm}px ${space.md + 4}px;
    border: none; border-radius: ${radius.md}px; cursor: pointer; text-align: left;
    background-color: transparent; color: ${neutral[600]};
    font-size: ${fontSize.sm}px; font-family: ${fontFamily.body};
    transition: background-color .15s ease, color .15s ease;
  }
  .cliyard-flow-item:hover { background-color: ${neutral[100]}; }
  .cliyard-flow-item[data-active="true"] { background-color: ${brand[50]}; }
  .cliyard-flow-item[data-active="true"] .cliyard-flow-name { color: ${brand[600]}; font-weight: 500; }
  .cliyard-flow-item[data-active="true"] .cliyard-flow-command { color: ${brand[500]}; }

  /* 表单输入框：1px 边框 + 轻阴影，focus 品牌蓝边框 + 光环 */
  .cliyard-field {
    width: 100%; border-radius: ${radius.md}px;
    border: 1px solid ${neutral[200]}; background-color: #FFFFFF;
    padding: ${space.sm}px ${space.md}px;
    font-size: ${fontSize.md}px; color: ${neutral[800]};
    font-family: ${fontFamily.mono};
    outline: none; box-shadow: ${shadow.sm}; box-sizing: border-box;
    transition: border-color .15s ease, box-shadow .15s ease;
  }
  .cliyard-field:focus { border-color: ${brand[500]}; box-shadow: 0 0 0 3px rgba(59,130,246,.15); }

  /* 历史表格行 hover */
  .cliyard-row { transition: background-color .15s ease; }
  .cliyard-row:hover { background-color: ${neutral[50]}; }
  .cliyard-row:last-child { border-bottom: none !important; }
`;

/* ---------- 基础常量 ---------- */

const baseFont: CSSProperties = { fontFamily: fontFamily.body };

/** 卡片外壳：白底 + 1px 边框 + 轻阴影 + 大圆角 */
const cardBase: CSSProperties = {
  backgroundColor: "#FFFFFF",
  border: `1px solid ${neutral[200]}`,
  borderRadius: radius.lg,
  boxShadow: shadow.sm,
};

/* ---------- 小组件 ---------- */

/** "repos list" → repos 用品牌蓝、list 用深色，突出资源维度 */
function CommandCell({ command }: { command: string }) {
  const idx = command.indexOf(" ");
  if (idx === -1)
    return (
      <span style={{ fontFamily: fontFamily.mono, fontWeight: 500, color: neutral[800] }}>
        {command}
      </span>
    );
  return (
    <span style={{ fontFamily: fontFamily.mono, fontWeight: 500 }}>
      <span style={{ color: brand[600] }}>{command.slice(0, idx)}</span>
      <span style={{ color: neutral[800] }}>{command.slice(idx)}</span>
    </span>
  );
}

/** 历史状态 pill：浅底 + 1px 彩边 + 深色文字（成功绿 / 失败红） */
function StatusPill({ status }: { status: HistoryRow["status"] }) {
  const t = statusColors[status === "success" ? "success" : "error"];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: space.xs,
        padding: `${space.xs - 1}px ${space.sm + 2}px`,
        borderRadius: radius.pill,
        backgroundColor: t.bg,
        border: `1px solid ${t.border}`,
        color: t.color,
        fontSize: fontSize.sm,
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
      {status === "success" ? "成功" : "失败"}
    </span>
  );
}

/** 步骤节点：成功=品牌蓝实心圆 / 运行中=浅蓝底蓝圈 + 呼吸小点 / 失败=红 */
function StepIcon({ status }: { status: Step["status"] }) {
  const base: CSSProperties = {
    display: "flex",
    width: 24,
    height: 24,
    flexShrink: 0,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    position: "relative",
  };
  if (status === "done")
    return (
      <span data-testid="step-icon" data-status="done" style={{ ...base, backgroundColor: brand[500], color: "#FFFFFF" }}>
        <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </span>
    );
  if (status === "error")
    return (
      <span data-testid="step-icon" data-status="error" style={{ ...base, backgroundColor: statusColors.error.color, color: "#FFFFFF" }}>
        <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round">
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </span>
    );
  if (status === "pending")
    return (
      <span data-testid="step-icon" data-status="pending" style={{ ...base, backgroundColor: "#FFFFFF", border: `1.5px solid ${neutral[200]}`, color: neutral[400] }}>
        <span aria-hidden style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: neutral[300] }} />
      </span>
    );
  return (
    <span data-testid="step-icon" data-status="running" style={{ ...base, backgroundColor: brand[50], border: `1.5px solid ${brand[500]}`, color: brand[500] }}>
      <span
        aria-hidden
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: brand[500],
          animation: "cliyard-breathe 1.2s ease-in-out infinite",
        }}
      />
    </span>
  );
}

/** 深色代码块行级语法着色（保持翠绿/天蓝/琥珀，纯展示层不改数据） */
function MonoLine({ line }: { line: string }) {
  // 请求行：GET https://... → 方法琥珀、URL 天蓝
  const reqM = line.match(/^([A-Z]{3,6})\s+(https?:\/\/\S+)(.*)$/);
  if (reqM)
    return (
      <>
        <span style={{ fontWeight: 600, color: "#FBBF24" }}>{reqM[1]}</span>
        <span style={{ color: "#7DD3FC" }}> {reqM[2]}</span>
        <span style={{ color: "#94A3B8" }}>{reqM[3]}</span>
      </>
    );
  // JSON 行："key": value → 键天蓝、值按类型着色
  const kvM = line.match(/^(\s*"[\w-]+"\s*:\s*)(.*?)(,?)$/);
  if (kvM) {
    const val = kvM[2];
    const valColor = val.startsWith('"')
      ? "#6EE7B7" // 字符串：翠绿
      : /^-?\d/.test(val)
        ? "#FBBF24" // 数字：琥珀
        : val.includes("{") || val.includes("[")
          ? "#7DD3FC" // 对象/数组：天蓝
          : "#C4B5FD"; // 其他：紫
    return (
      <>
        <span style={{ color: "#7DD3FC" }}>{kvM[1]}</span>
        <span style={{ color: valColor }}>{kvM[2]}</span>
        <span style={{ color: "#64748B" }}>{kvM[3]}</span>
      </>
    );
  }
  // 请求头：Key: value
  const headM = line.match(/^([\w-]+):\s+(.*)$/);
  if (headM)
    return (
      <>
        <span style={{ color: "#94A3B8" }}>{headM[1]}:</span>
        <span style={{ color: "#E2E8F0" }}> {headM[2]}</span>
      </>
    );
  return <>{line}</>;
}

/** labels badge 按内容分配语义色（浅底 + 1px 彩边 + 深色文字） */
function labelBadgeTheme(label: string): StatusTheme {
  if (label === "已调试") return statusColors.success;
  if (label === "v2") return statusColors.warning;
  return { color: brand[600], bg: brand[50], border: brand[200] };
}

/** 命令参数表单字段：label mono 小字，输入框 token 化 */
function FormField({
  label,
  required,
  kind,
  placeholder,
  value,
}: {
  label: string;
  required?: boolean;
  kind: "text" | "number" | "select" | "password" | "switch";
  placeholder?: string;
  value?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: space.sm }}>
      <label style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs, fontWeight: 600, color: neutral[700], ...baseFont }}>
        {label}
        {required && <span style={{ color: statusColors.error.color, marginLeft: 2 }}>*</span>}
      </label>
      {kind === "select" ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderRadius: radius.md,
            border: `1px solid ${neutral[200]}`,
            backgroundColor: "#FFFFFF",
            padding: `${space.sm}px ${space.md}px`,
            fontSize: fontSize.md,
            color: neutral[700],
            boxShadow: shadow.sm,
            cursor: "default",
            ...baseFont,
          }}
        >
          <span style={{ fontFamily: fontFamily.mono }}>{value}</span>
          <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke={neutral[400]} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </div>
      ) : kind === "switch" ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderRadius: radius.md,
            border: `1px solid ${neutral[200]}`,
            backgroundColor: "#FFFFFF",
            padding: `${space.sm}px ${space.md}px`,
            boxShadow: shadow.sm,
            ...baseFont,
          }}
        >
          <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.md, color: neutral[400] }}>false</span>
          <span style={{ width: 36, height: 20, borderRadius: radius.pill, backgroundColor: neutral[200], padding: 2, display: "inline-flex" }}>
            <span style={{ display: "block", width: 16, height: 16, borderRadius: "50%", backgroundColor: "#FFFFFF", boxShadow: "0 1px 2px rgba(15,23,42,.15)" }} />
          </span>
        </div>
      ) : (
        <input
          type={kind === "password" ? "password" : "text"}
          placeholder={placeholder}
          defaultValue={value}
          className="cliyard-field"
        />
      )}
    </div>
  );
}

/* ---------- 主组件 ---------- */

function CommandPanel({ device, deviceWidth }: PrototypeRenderProps) {
  const [active, setActive] = useState("repos.list");
  const [activeTab, setActiveTab] = useState<"steps" | "history">("steps");
  const [sideTab, setSideTab] = useState<"commands" | "flows">("commands");
  const [activeFlow, setActiveFlow] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const activeItem = tree
    .flatMap((g) => g.items.map((it) => ({ g: g.group, ...it })))
    .find((it) => `${it.g}.${it.name}` === active)!;

  const currentFlow = flows.find((f) => f.name === activeFlow) ?? flows[0];

  // 左侧搜索：命令按 group/name/desc，flow 按 name/description/command
  const filteredGroups = tree
    .map((g) => ({
      ...g,
      items: g.items.filter((it) => `${g.group}.${it.name}`.includes(search) || it.desc.includes(search)),
    }))
    .filter((g) => g.items.length > 0);
  const filteredFlows = flows.filter(
    (f) => f.name.includes(search) || f.description.includes(search) || f.command.includes(search),
  );

  // 右侧执行步骤：flow 时展示编排步骤（use 徽标 + pending 态 + 进度 N/N）
  const shownSteps = sideTab === "flows" ? flowSteps : steps;
  const flowStepTotal = flowSteps.filter((s) => s.use).length;
  const flowStepDone = flowSteps.filter((s) => s.status === "done" && s.use).length;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100%",
        width: deviceWidth,
        maxWidth: "100%",
        backgroundColor: neutral[50],
        ...baseFont,
      }}
    >
      <style>{cliCss}</style>

      {/* 顶栏：浅色白底 height 60（对齐 aiagents NavTopBar） */}
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
        {/* 左：标题 + spec 副标题 */}
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

        {/* 右：运行状态 badge + 功能按钮 */}
        <div style={{ display: "flex", alignItems: "center", gap: space.sm }}>
          <span
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
          <button type="button" className="cliyard-text-btn" onClick={() => setActiveTab("history")}>
            历史
          </button>
          <button type="button" className="cliyard-text-btn">
            认证
          </button>
          <button type="button" className="cliyard-text-btn">
            设置
          </button>
        </div>
      </header>

      {/* 内容区：三栏 */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", gap: space.lg, padding: space.xl }}>
        {/* ① 命令树 / flow 列表（顶部 tab 切换） */}
        <aside data-testid="command-tree" style={{ width: 224, flexShrink: 0, ...cardBase, padding: space.lg, overflowY: "auto" }}>
          {/* 左侧 tab：命令 | Flow（选中态 2px 品牌蓝下划线，对齐右侧 tab 风格） */}
          <div style={{ display: "flex", alignItems: "flex-end", borderBottom: `1px solid ${neutral[200]}`, marginBottom: space.md }}>
            {(
              [
                { id: "commands", label: "命令" },
                { id: "flows", label: "Flow" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                data-testid="side-tab"
                data-active={sideTab === t.id ? "true" : "false"}
                onClick={() => setSideTab(t.id)}
                style={{
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  padding: `${space.sm}px ${space.md}px`,
                  marginBottom: -1,
                  fontSize: fontSize.md,
                  fontFamily: fontFamily.body,
                  borderBottom: `2px solid ${sideTab === t.id ? brand[500] : "transparent"}`,
                  color: sideTab === t.id ? brand[600] : neutral[500],
                  fontWeight: sideTab === t.id ? 500 : 400,
                  transition: "color .15s ease, border-color .15s ease",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* 搜索（过滤当前 tab 内容） */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: space.sm,
              padding: `${space.sm}px ${space.md}px`,
              borderRadius: radius.md,
              backgroundColor: neutral[50],
              border: `1px solid ${neutral[200]}`,
              color: neutral[400],
              fontSize: fontSize.sm,
              marginBottom: space.lg,
              ...baseFont,
            }}
          >
            <IconSearch className="size-3.5" />
            <input
              data-testid="tree-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={sideTab === "commands" ? "搜索命令…" : "搜索 flow…"}
              style={{
                flex: 1,
                minWidth: 0,
                border: "none",
                outline: "none",
                background: "transparent",
                fontFamily: fontFamily.body,
                fontSize: fontSize.sm,
                color: neutral[700],
              }}
            />
          </div>

          {sideTab === "commands" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: space.lg }}>
              {filteredGroups.map((g) => (
                <div key={g.group}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: `0 ${space.xs}px`, marginBottom: space.sm }}>
                    <span style={{ fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.06, color: neutral[400] }}>
                      {g.group}
                    </span>
                    <span style={{ fontSize: fontSize.xs, color: neutral[300] }}>{g.desc}</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {g.items.map((it) => {
                      const id = `${g.group}.${it.name}`;
                      const on = id === active;
                      return (
                        <button
                          key={id}
                          type="button"
                          data-testid="tree-item"
                          data-active={on ? "true" : "false"}
                          onClick={() => setActive(id)}
                          className="cliyard-tree-item"
                        >
                          {on && (
                            <span
                              aria-hidden
                              style={{
                                position: "absolute",
                                left: 0,
                                top: "50%",
                                transform: "translateY(-50%)",
                                width: 3,
                                height: 18,
                                borderRadius: radius.pill,
                                backgroundColor: brand[500],
                              }}
                            />
                          )}
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.name}</span>
                          {it.tags?.includes("danger") && (
                            <span
                              aria-hidden
                              style={{ marginLeft: "auto", width: 6, height: 6, flexShrink: 0, borderRadius: "50%", backgroundColor: statusColors.error.color }}
                            />
                          )}
                          {it.labels.map((lb) => {
                            const t = labelBadgeTheme(lb);
                            return (
                              <span
                                key={lb}
                                style={{
                                  marginLeft: "auto",
                                  borderRadius: radius.pill,
                                  padding: "0 6px",
                                  backgroundColor: t.bg,
                                  border: `1px solid ${t.border}`,
                                  color: t.color,
                                  fontSize: 9,
                                  fontWeight: 600,
                                  lineHeight: "16px",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {lb}
                              </span>
                            );
                          })}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {filteredFlows.map((f) => {
                const on = f.name === currentFlow.name;
                return (
                  <button
                    key={f.name}
                    type="button"
                    data-testid="flow-item"
                    data-active={on ? "true" : "false"}
                    onClick={() => setActiveFlow(f.name)}
                    className="cliyard-flow-item"
                  >
                    {on && (
                      <span
                        aria-hidden
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 14,
                          transform: "translateY(-50%)",
                          width: 3,
                          height: 18,
                          borderRadius: radius.pill,
                          backgroundColor: brand[500],
                        }}
                      />
                    )}
                    <span style={{ display: "flex", alignItems: "center", gap: space.sm, minWidth: 0 }}>
                      <span className="cliyard-flow-name" style={{ fontFamily: fontFamily.mono, fontSize: fontSize.sm, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {f.name}
                      </span>
                      <span
                        style={{
                          flexShrink: 0,
                          borderRadius: radius.pill,
                          padding: "0 6px",
                          backgroundColor: brand[50],
                          border: `1px solid ${brand[200]}`,
                          color: brand[600],
                          fontSize: 9,
                          fontWeight: 600,
                          lineHeight: "14px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        flow
                      </span>
                      <span className="cliyard-flow-command" style={{ marginLeft: "auto", fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[400], overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {f.command}
                      </span>
                    </span>
                    <span style={{ fontSize: fontSize.xs, color: neutral[500], lineHeight: 1.5, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                      {f.description}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        {/* ② 命令 / flow 表单 */}
        <section data-testid="command-form" style={{ width: 320, flexShrink: 0, ...cardBase, padding: space.lg, overflowY: "auto", display: "flex", flexDirection: "column" }}>
          {sideTab === "commands" ? (
            <>
              <div style={{ marginBottom: space.lg }}>
                <div style={{ display: "flex", alignItems: "center", gap: space.sm }}>
                  <h2 style={{ margin: 0, fontFamily: fontFamily.mono, fontSize: fontSize.lg, fontWeight: 600, color: neutral[900] }}>
                    {activeItem.g}.{activeItem.name}
                  </h2>
                  {activeItem.labels.map((lb) => {
                    const t = labelBadgeTheme(lb);
                    return (
                      <span
                        key={lb}
                        style={{
                          borderRadius: radius.pill,
                          padding: "0 6px",
                          backgroundColor: t.bg,
                          border: `1px solid ${t.border}`,
                          color: t.color,
                          fontSize: 9,
                          fontWeight: 600,
                          lineHeight: "16px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {lb}
                      </span>
                    );
                  })}
                </div>
                <p style={{ margin: `${space.xs}px 0 0`, fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[400] }}>
                  {activeItem.desc} · GET /api/v1/{activeItem.g} · 由 YAML spec 自动渲染
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: space.lg }}>
                <FormField label="name" placeholder="仓库名称" value="cliyard" />
                <FormField label="format" kind="select" value="json" />
                <FormField label="page_size" kind="number" placeholder="默认 20" value="20" />
                <FormField label="verbose" kind="switch" />
                <FormField label="token" kind="password" placeholder="认证 token（password 框）" value="saved-profile" />
              </div>
            </>
          ) : (
            <>
              <div style={{ marginBottom: space.lg }}>
                <div style={{ display: "flex", alignItems: "center", gap: space.sm }}>
                  <h2 style={{ margin: 0, fontFamily: fontFamily.mono, fontSize: fontSize.lg, fontWeight: 600, color: neutral[900] }}>
                    {currentFlow.name}
                  </h2>
                  <span
                    style={{
                      borderRadius: radius.pill,
                      padding: "0 8px",
                      backgroundColor: neutral[100],
                      border: `1px solid ${neutral[200]}`,
                      color: neutral[600],
                      fontSize: fontSize.xs,
                      fontWeight: 500,
                      fontFamily: fontFamily.mono,
                      lineHeight: "18px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {currentFlow.command}
                  </span>
                  <span
                    style={{
                      flexShrink: 0,
                      borderRadius: radius.pill,
                      padding: "0 6px",
                      backgroundColor: brand[50],
                      border: `1px solid ${brand[200]}`,
                      color: brand[600],
                      fontSize: 9,
                      fontWeight: 600,
                      lineHeight: "16px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    flow
                  </span>
                </div>
                <p style={{ margin: `${space.xs}px 0 0`, fontSize: fontSize.xs, color: neutral[400], ...baseFont }}>
                  {currentFlow.description} · 由 _flows.yaml 注册 · {currentFlow.stepCount} 个编排步骤
                </p>
              </div>

              {currentFlow.params && currentFlow.params.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: space.lg }}>
                  {currentFlow.params.map((p) => (
                    <FormField key={p.name} label={p.name} required={p.required} placeholder={p.description} />
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flex: 1,
                    minHeight: 120,
                    borderRadius: radius.md,
                    border: `1px dashed ${neutral[200]}`,
                    backgroundColor: neutral[50],
                    color: neutral[400],
                    fontSize: fontSize.sm,
                    ...baseFont,
                  }}
                >
                  该流程无需参数
                </div>
              )}
            </>
          )}

          <div style={{ display: "flex", gap: space.sm, borderTop: `1px solid ${neutral[100]}`, paddingTop: space.lg, marginTop: "auto" }}>
            <button type="button" data-testid="run-button" className="cliyard-pill-btn" style={{ flex: 1, padding: `${space.sm + 2}px ${space.lg}px` }}>
              {sideTab === "commands" ? "执行" : "运行流程"}
            </button>
            <button type="button" className="cliyard-outline-btn" style={{ flex: 1, justifyContent: "center" }}>
              重置
            </button>
          </div>
        </section>

        {/* ③ 执行步骤 / 历史记录（tab 切换） */}
        <section data-testid="right-panel" style={{ minWidth: 0, flex: 1, ...cardBase, overflowY: "auto" }}>
          {/* tab bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: `1px solid ${neutral[200]}`,
              backgroundColor: neutral[50],
              padding: `0 ${space.sm}px`,
              borderRadius: `${radius.lg}px ${radius.lg}px 0 0`,
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              {(
                [
                  { id: "steps", label: "执行步骤" },
                  { id: "history", label: "历史记录" },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  data-testid="panel-tab"
                  data-active={activeTab === t.id ? "true" : "false"}
                  onClick={() => setActiveTab(t.id)}
                  style={{
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    padding: `${space.md}px ${space.lg}px`,
                    marginBottom: -1,
                    fontSize: fontSize.md,
                    fontFamily: fontFamily.body,
                    borderBottom: `2px solid ${activeTab === t.id ? brand[500] : "transparent"}`,
                    color: activeTab === t.id ? brand[600] : neutral[500],
                    fontWeight: activeTab === t.id ? 500 : 400,
                    transition: "color .15s ease, border-color .15s ease",
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {activeTab === "steps" ? (
              <div style={{ display: "flex", alignItems: "center", gap: space.sm, paddingBottom: space.sm, paddingRight: space.sm }}>
                <span style={{ borderRadius: radius.sm, backgroundColor: "#FFFFFF", padding: "2px 8px", fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500], border: `1px solid ${neutral[200]}` }}>
                  {sideTab === "flows" ? `编排步骤 ${flowStepDone + 1}/${flowStepTotal}` : "耗时 129ms"}
                </span>
                <button type="button" className="cliyard-outline-btn">
                  <IconRefresh className="size-3.5" />
                  重新执行
                </button>
                <button type="button" className="cliyard-text-btn">
                  复制
                </button>
                <button type="button" className="cliyard-text-btn">
                  清空
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: space.sm, paddingBottom: space.sm, paddingRight: space.sm }}>
                <button type="button" className="cliyard-outline-btn">
                  清空记录
                </button>
                <button type="button" className="cliyard-outline-btn">
                  <IconRefresh className="size-3.5" />
                  刷新
                </button>
              </div>
            )}
          </div>

          {activeTab === "steps" ? (
            /* 执行步骤时间线 */
            <ol style={{ display: "flex", flexDirection: "column", margin: 0, padding: space.lg, listStyle: "none" }}>
              {shownSteps.map((s, i) => (
                <li key={s.title} style={{ position: "relative", display: "flex", gap: space.md, paddingBottom: space.lg }}>
                  {i !== shownSteps.length - 1 && (
                    <span aria-hidden style={{ position: "absolute", left: 11.5, top: 26, bottom: 0, width: 1, backgroundColor: neutral[200] }} />
                  )}
                  <StepIcon status={s.status} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: space.sm }}>
                      <span style={{ fontSize: fontSize.sm, fontWeight: 600, color: s.status === "error" ? statusColors.error.color : neutral[800] }}>
                        {s.title}
                      </span>
                      <span style={{ borderRadius: radius.sm, backgroundColor: neutral[100], padding: "2px 6px", fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: neutral[500] }}>
                        {s.time}
                      </span>
                      {s.use && (
                        <span style={{ borderRadius: radius.sm, backgroundColor: brand[50], border: `1px solid ${brand[200]}`, padding: "2px 6px", fontFamily: fontFamily.mono, fontSize: fontSize.xs, color: brand[600] }}>
                          use: {s.use}
                        </span>
                      )}
                      {s.status === "error" && (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: space.xs,
                            padding: "1px 8px",
                            borderRadius: radius.pill,
                            backgroundColor: statusColors.error.bg,
                            border: `1px solid ${statusColors.error.border}`,
                            color: statusColors.error.color,
                            fontSize: fontSize.xs,
                            fontWeight: 500,
                            ...baseFont,
                          }}
                        >
                          失败
                        </span>
                      )}
                      {s.status === "running" && (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: space.xs,
                            padding: "1px 8px",
                            borderRadius: radius.pill,
                            backgroundColor: statusColors.running.bg,
                            border: `1px solid ${statusColors.running.border}`,
                            color: statusColors.running.color,
                            fontSize: fontSize.xs,
                            fontWeight: 500,
                            ...baseFont,
                          }}
                        >
                          <span
                            aria-hidden
                            style={{
                              width: 5,
                              height: 5,
                              borderRadius: "50%",
                              backgroundColor: statusColors.running.color,
                              animation: "cliyard-breathe 1.2s ease-in-out infinite",
                            }}
                          />
                          执行中
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: space.sm, overflow: "hidden", borderRadius: radius.md, border: `1px solid ${neutral[200]}`, backgroundColor: "#FFFFFF" }}>
                      {s.mono ? (
                        <pre style={{ margin: 0, overflowX: "auto", backgroundColor: neutral[900], padding: `${space.sm + 2}px ${space.md}px`, fontFamily: fontFamily.mono, fontSize: fontSize.xs, lineHeight: 1.7, color: "#6EE7B7" }}>
                          {s.body.map((line, i) => (
                            <span key={i} style={{ display: "block", whiteSpace: "pre" }}>
                              <span style={{ display: "inline-block", width: 16, marginRight: space.md, textAlign: "right", userSelect: "none", color: neutral[600] }}>
                                {i + 1}
                              </span>
                              <MonoLine line={line} />
                            </span>
                          ))}
                        </pre>
                      ) : (
                        <pre style={{ margin: 0, overflowX: "auto", backgroundColor: neutral[50], padding: `${space.sm + 2}px ${space.md}px`, fontSize: fontSize.xs, lineHeight: 1.7, ...baseFont }}>
                          {s.body.map((line, i) => (
                            <span
                              key={i}
                              style={{
                                display: "block",
                                whiteSpace: "pre",
                                color: line.startsWith(" ") ? neutral[500] : neutral[700],
                                fontWeight: line.startsWith(" ") ? 400 : 500,
                              }}
                            >
                              {line || "\u00A0"}
                            </span>
                          ))}
                        </pre>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            /* 历史记录表格 */
            <div style={{ padding: space.lg }}>
              <div style={{ overflow: "hidden", borderRadius: radius.md, border: `1px solid ${neutral[200]}` }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: fontSize.sm, ...baseFont }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${neutral[200]}`, backgroundColor: neutral[50] }}>
                      <th style={{ padding: `${space.sm + 2}px ${space.lg}px`, fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05, color: neutral[400] }}>
                        开始时间
                      </th>
                      <th style={{ padding: `${space.sm + 2}px ${space.lg}px`, fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05, color: neutral[400] }}>
                        命令
                      </th>
                      <th style={{ padding: `${space.sm + 2}px ${space.lg}px`, fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05, color: neutral[400] }}>
                        状态
                      </th>
                      <th style={{ padding: `${space.sm + 2}px ${space.lg}px`, fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05, color: neutral[400] }}>
                        耗时
                      </th>
                      <th style={{ padding: `${space.sm + 2}px ${space.lg}px`, fontSize: fontSize.xs, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.05, color: neutral[400] }}>
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRows.map((r) => (
                      <tr key={r.time + r.command} className="cliyard-row" style={{ borderBottom: `1px solid ${neutral[100]}` }}>
                        <td style={{ padding: `${space.md}px ${space.lg}px`, fontFamily: fontFamily.mono, color: neutral[500], whiteSpace: "nowrap" }}>
                          {r.time}
                        </td>
                        <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                          <CommandCell command={r.command} />
                        </td>
                        <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                          <StatusPill status={r.status} />
                        </td>
                        <td style={{ padding: `${space.md}px ${space.lg}px`, fontFamily: fontFamily.mono, color: neutral[500], whiteSpace: "nowrap" }}>
                          {r.duration}
                        </td>
                        <td style={{ padding: `${space.md}px ${space.lg}px` }}>
                          <button type="button" className="cliyard-text-btn" data-testid="replay-button">
                            重放
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: space.md, display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: fontSize.xs, color: neutral[400], ...baseFont }}>
                <span style={{ fontFamily: fontFamily.mono, fontSize: fontSize.xs }}>共 {historyRows.length} 条 · 第 1 / 1 页</span>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* 底部 footer */}
      <footer
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: `${space.sm}px ${space.xl}px`,
          borderTop: `1px solid ${neutral[200]}`,
          backgroundColor: "#FFFFFF",
          fontSize: fontSize.xs,
          color: neutral[400],
          ...baseFont,
        }}
      >
        <span>cliyard serve · 进程内执行（CliRunner）· SSE 实时推送</span>
        <span>6 个命令 · 2 个资源 · {flows.length} 个 flow</span>
      </footer>
    </div>
  );
}

const def: PrototypeDef = {
  meta: {
    id: "command-panel",
    name: "主界面",
    group: "核心",
    description: "命令树 + 自动表单 + 执行步骤/历史（三栏，历史在右侧 tab）",
    device: "desktop",
  },
  Component: CommandPanel,
};

export default def;
