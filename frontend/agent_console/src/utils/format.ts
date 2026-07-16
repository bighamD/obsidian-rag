import type { RunStatus } from "@/types/production";

export function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs === null || durationMs === undefined) {
    return "-";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(durationMs < 10000 ? 1 : 0)} s`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        month: "numeric",
        day: "numeric",
      }).format(date);
}

export function shortId(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-5)}` : value;
}

export function statusLabel(status: RunStatus | "idle"): string {
  return {
    idle: "就绪",
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
  }[status];
}

export function renderSafeMarkdown(text: string): string {
  const escaped = text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const inline = escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");

  return inline
    .split(/\n{2,}/)
    .map((paragraph: string) => `<p>${paragraph.replaceAll("\n", "<br>")}</p>`)
    .join("");
}
