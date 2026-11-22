import { describe, expect, it } from "vitest";
import { formatTimestamp } from "./formatters";

describe("formatTimestamp", () => {
  it("formats zero seconds", () => {
    expect(formatTimestamp(0)).toBe("00:00");
  });

  it("formats sub-minute durations", () => {
    expect(formatTimestamp(45)).toBe("00:45");
  });

  it("rolls over exactly at the one-hour boundary", () => {
    expect(formatTimestamp(3600)).toBe("1:00:00");
  });

  it("formats durations over one hour (regression for COR-002)", () => {
    // 2h05m03s previously rendered as "125:03" because minutes never
    // rolled into an hours segment.
    expect(formatTimestamp(7503)).toBe("2:05:03");
  });

  it("formats durations over ten hours", () => {
    expect(formatTimestamp(37_800)).toBe("10:30:00");
  });

  it("rounds down fractional seconds", () => {
    expect(formatTimestamp(125.9)).toBe("02:05");
  });

  it("falls back to 00:00 for missing values", () => {
    expect(formatTimestamp(undefined)).toBe("00:00");
    expect(formatTimestamp(null)).toBe("00:00");
    expect(formatTimestamp(Number.NaN)).toBe("00:00");
  });
});
