import { describe, expect, it } from "vitest";

import { formatDuration, renderSafeMarkdown, statusLabel } from "./format";

describe("console format helpers", () => {
  it("formats runtime duration for the inspector", () => {
    expect(formatDuration(320)).toBe("320 ms");
    expect(formatDuration(1280)).toBe("1.3 s");
  });

  it("escapes answer HTML before applying the small Markdown subset", () => {
    expect(renderSafeMarkdown("**安全** <script>alert(1)</script>")).toContain("<strong>安全</strong>");
    expect(renderSafeMarkdown("<script>alert(1)</script>")).toContain("&lt;script&gt;");
  });

  it("maps visible status labels", () => {
    expect(statusLabel("running")).toBe("运行中");
    expect(statusLabel("idle")).toBe("就绪");
  });
});
