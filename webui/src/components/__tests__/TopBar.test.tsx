import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import TopBar from "../TopBar";

describe("TopBar", () => {
  it("默认渲染：不传 service 时显示 fallback 标题和文字 logo", () => {
    render(<TopBar onAuthClick={vi.fn()} />);
    expect(screen.getByText("cliyard-web")).toBeInTheDocument();
    expect(screen.getByText("C")).toBeInTheDocument();
    expect(screen.queryByTestId("topbar-logo-img")).not.toBeInTheDocument();
  });

  it("无 service 时认证按钮正常渲染", () => {
    render(<TopBar onAuthClick={vi.fn()} />);
    expect(screen.getByText("登录认证")).toBeInTheDocument();
  });

  it("有 service.name 但无 branding 时回退到 service.name 和首字母", () => {
    render(<TopBar service={{ name: "mycli", description: "My CLI Tool" }} onAuthClick={vi.fn()} />);
    expect(screen.getByText("mycli")).toBeInTheDocument();
    expect(screen.getByText("My CLI Tool")).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument();
  });

  it("有 branding.title 时覆盖 service.name", () => {
    render(
      <TopBar
        service={{
          name: "mycli",
          description: "My CLI Tool",
          web: { branding: { title: "定制标题", subtitle: "定制副标题" } },
        }}
        onAuthClick={vi.fn()}
      />,
    );
    expect(screen.getByText("定制标题")).toBeInTheDocument();
    expect(screen.getByText("定制副标题")).toBeInTheDocument();
  });

  it("有 logo_url 时渲染 img 而非文字 logo", () => {
    render(
      <TopBar
        service={{
          name: "mycli",
          description: "",
          web: { branding: { logo_url: "https://example.com/logo.png" } },
        }}
        onAuthClick={vi.fn()}
      />,
    );
    const img = screen.getByTestId("topbar-logo-img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/logo.png");
    expect(screen.queryByText("M")).not.toBeInTheDocument();
  });

  it("无 subtitle 时副标题行不渲染", () => {
    render(
      <TopBar
        service={{ name: "mycli", description: "" }}
        onAuthClick={vi.fn()}
      />,
    );
    // 描述为空字符串时，subtitle 条件渲染不产生 dom 节点
    expect(screen.getByText("mycli")).toBeInTheDocument();
    // 确认副标题行未渲染（只有 title 行）
    expect(screen.getByTestId("topbar-title").textContent).toBe("mycli");
  });

  it("有 logo_text 时渲染指定文字 logo", () => {
    render(
      <TopBar
        service={{
          name: "mycli",
          description: "",
          web: { branding: { logo_text: "X" } },
        }}
        onAuthClick={vi.fn()}
      />,
    );
    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.queryByText("M")).not.toBeInTheDocument();
  });
});