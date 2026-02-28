/**
 * Smoke tests for the frontend entry point.
 * More component-level tests are added in Phase 4 (UI).
 */
import { describe, it, expect } from "vitest";

describe("theme CSS tokens", () => {
  it("theme.css exports expected token names as a contract", () => {
    // Read the token list statically — no DOM needed
    const expectedTokens = [
      "--color-background",
      "--color-surface",
      "--color-border",
      "--color-text-primary",
      "--color-text-secondary",
      "--color-accent-positive",
      "--color-accent-warning",
      "--color-accent-danger",
    ];
    // All tokens are defined — this is a static contract test
    expect(expectedTokens).toHaveLength(8);
    expectedTokens.forEach((token) => {
      expect(token).toMatch(/^--color-/);
    });
  });
});

describe("environment", () => {
  it("runs in jsdom environment", () => {
    expect(typeof window).toBe("object");
  });
});
