/**
 * Tests for base UI components: Card, Badge, ProgressBar, Chart.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { Card } from "../src/components/Card";
import { Badge } from "../src/components/Badge";
import { ProgressBar } from "../src/components/ProgressBar";
import { Chart } from "../src/components/Chart";

// ── Card ──────────────────────────────────────────────────────────────────────

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Hello Card</Card>);
    expect(screen.getByText("Hello Card")).toBeTruthy();
  });

  it("applies default medium padding class", () => {
    const { container } = render(<Card>content</Card>);
    expect(container.firstChild?.toString()).toBeTruthy();
    // Check the rendered element contains padding class
    const el = container.firstElementChild!;
    expect(el.className).toContain("p-5");
  });

  it("applies custom padding preset", () => {
    const { container } = render(<Card padding="lg">content</Card>);
    expect(container.firstElementChild!.className).toContain("p-7");
  });

  it('applies no padding when padding="none"', () => {
    const { container } = render(<Card padding="none">content</Card>);
    const cls = container.firstElementChild!.className;
    expect(cls).not.toContain("p-5");
    expect(cls).not.toContain("p-7");
  });

  it("forwards extra className", () => {
    const { container } = render(<Card className="extra-class">content</Card>);
    expect(container.firstElementChild!.className).toContain("extra-class");
  });

  it("always has rounded-xl class", () => {
    const { container } = render(<Card>content</Card>);
    expect(container.firstElementChild!.className).toContain("rounded-xl");
  });
});

// ── Badge ─────────────────────────────────────────────────────────────────────

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Critical</Badge>);
    expect(screen.getByText("Critical")).toBeTruthy();
  });

  it("renders as a <span>", () => {
    const { container } = render(<Badge>test</Badge>);
    expect(container.firstElementChild!.tagName).toBe("SPAN");
  });

  it("applies variant-specific class for critical", () => {
    const { container } = render(<Badge variant="critical">Critical</Badge>);
    expect(container.firstElementChild!.className).toContain("accent-danger");
  });

  it("applies variant-specific class for warning (medium)", () => {
    const { container } = render(<Badge variant="medium">Medium</Badge>);
    expect(container.firstElementChild!.className).toContain("accent-warning");
  });

  it("applies variant-specific class for positive (low)", () => {
    const { container } = render(<Badge variant="low">Low</Badge>);
    expect(container.firstElementChild!.className).toContain("accent-positive");
  });

  it("defaults to neutral variant", () => {
    const { container } = render(<Badge>default</Badge>);
    expect(container.firstElementChild!.className).toContain("text-secondary");
  });

  it("has uppercase and tracking-wide classes", () => {
    const { container } = render(<Badge>label</Badge>);
    const cls = container.firstElementChild!.className;
    expect(cls).toContain("uppercase");
    expect(cls).toContain("tracking-wide");
  });
});

// ── ProgressBar ───────────────────────────────────────────────────────────────

describe("ProgressBar", () => {
  it("renders a progressbar role element", () => {
    render(<ProgressBar value={50} />);
    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  it("sets aria-valuenow to the clamped value", () => {
    render(<ProgressBar value={60} aria-label="progress" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "60",
    );
  });

  it("clamps value above 100 to 100", () => {
    render(<ProgressBar value={150} aria-label="progress" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "100",
    );
  });

  it("clamps value below 0 to 0", () => {
    render(<ProgressBar value={-10} aria-label="progress" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "0",
    );
  });

  it("shows label text when showLabel is true", () => {
    render(<ProgressBar value={42} showLabel />);
    expect(screen.getByText("42%")).toBeTruthy();
  });

  it("does not show label text when showLabel is false (default)", () => {
    render(<ProgressBar value={42} />);
    expect(screen.queryByText("42%")).toBeNull();
  });

  it("applies aria-label to the progressbar element", () => {
    render(<ProgressBar value={50} aria-label="scan progress" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-label")).toBe(
      "scan progress",
    );
  });
});

// ── Chart ─────────────────────────────────────────────────────────────────────

describe("Chart", () => {
  it("renders an SVG element", () => {
    const { container } = render(<Chart value={75} />);
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it('renders with role="img" on the SVG', () => {
    render(<Chart value={50} aria-label="chart" />);
    expect(screen.getByRole("img")).toBeTruthy();
  });

  it("applies aria-label to the SVG", () => {
    render(<Chart value={50} aria-label="50 percent" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe(
      "50 percent",
    );
  });

  it("renders the label in the centre when provided", () => {
    render(<Chart value={75} label="75%" />);
    expect(screen.getByText("75%")).toBeTruthy();
  });

  it("does not render a centre label when not provided", () => {
    const { container } = render(<Chart value={75} />);
    // The label overlay div sits inside the outer wrapper and has absolute positioning
    // When label is undefined the conditional branch is skipped — no extra div is rendered
    const svgCount = container.querySelectorAll("svg").length;
    expect(svgCount).toBe(1);
    // No text content should appear when label is omitted
    expect(container.textContent).toBe("");
  });

  it("uses the provided size for SVG dimensions", () => {
    const { container } = render(<Chart value={50} size={120} />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("width")).toBe("120");
    expect(svg.getAttribute("height")).toBe("120");
  });

  it("clamps value above 100", () => {
    // Should not throw and should produce a valid dashOffset
    expect(() => render(<Chart value={150} />)).not.toThrow();
  });

  it("clamps value below 0", () => {
    expect(() => render(<Chart value={-5} />)).not.toThrow();
  });
});
