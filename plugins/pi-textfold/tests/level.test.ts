import { describe, expect, test } from "vitest";

import { KEY, levelAtColumn, levelRow, parseLevelArg, type Level, type Paint } from "../extension/level";

describe("parseLevelArg", () => {
  const cur: Level = 3;

  test("no argument cycles to the next level and wraps", () => {
    expect(parseLevelArg("", cur).level).toBe(4);
    expect(parseLevelArg("", 5).level).toBe(1);
  });

  test("off and full mean Full", () => {
    expect(parseLevelArg("off", cur).level).toBe(1);
    expect(parseLevelArg("full", cur).level).toBe(1);
  });

  test("level names and numbers both work, in any case", () => {
    expect(parseLevelArg("brief", cur).level).toBe(2);
    expect(parseLevelArg("GIST", cur).level).toBe(5);
    expect(parseLevelArg("2", cur).level).toBe(2);
  });

  test("out-of-range and unknown words keep the level with an error", () => {
    const bad = parseLevelArg("banana", cur);
    expect(bad.level).toBeUndefined();
    expect(bad.error).toContain("banana");
    expect(parseLevelArg("9", cur).level).toBeUndefined();
  });
});

describe("levelRow", () => {
  const mark: Paint = { label: (s) => s, current: (s) => `[${s}]`, other: (s) => s };

  test("names the five levels with their keys and marks the one read at", () => {
    const row = levelRow(3, 200, mark);
    expect(row).toBe("fold  1 Full  2 Brief  [3 Points]  4 Outline  5 Gist  · Alt+1…5");
  });

  test("never runs past the width: the hint goes first, then the other levels", () => {
    expect(levelRow(1, 55, mark)).toBe("fold  [1 Full]  2 Brief  3 Points  4 Outline  5 Gist");
    expect(levelRow(4, 20, mark)).toBe("fold [4 Outline]");
    for (const width of [20, 40, 55, 70, 120]) expect(levelRow(5, width, { ...mark, current: (s) => s }).length).toBeLessThanOrEqual(width);
  });

  test("taught keys show their own glyphs in the hint instead of lying about Alt+1…5", () => {
    const taught = { "1": "alt+&", "2": "alt+2", "3": "alt+'", "4": "alt+4", "5": "alt+(" };
    const row = levelRow(3, 200, mark, taught);
    expect(row).toBe("fold  1 Full  2 Brief  [3 Points]  4 Outline  5 Gist  · Alt+&…(");
  });

  test("a partial teaching falls back to the default hint", () => {
    expect(levelRow(3, 200, mark, { "1": "alt+&" })).toContain("· Alt+1…5");
  });
});

describe("levelAtColumn", () => {
  // Plain row: "fold  1 Full  2 Brief  [3 Points]  4 Outline  5 Gist  · Alt+1…5"
  // stripped of paint the segments sit at fixed offsets; a click names its level.
  const row = "fold  1 Full  2 Brief  3 Points  4 Outline  5 Gist  · Alt+1…5";

  test("each level segment maps to its level", () => {
    expect(levelAtColumn(row, 6)).toBe(1); // "1 Full" starts at 6
    expect(levelAtColumn(row, 10)).toBe(1);
    expect(levelAtColumn(row, 14)).toBe(2);
    expect(levelAtColumn(row, 24)).toBe(3);
    expect(levelAtColumn(row, 36)).toBe(4);
    expect(levelAtColumn(row, 48)).toBe(5);
  });

  test("the label, the gaps, and the hint map to nothing — clicks must land on a level", () => {
    expect(levelAtColumn(row, 0)).toBeUndefined();
    expect(levelAtColumn(row, 4)).toBeUndefined();
    expect(levelAtColumn(row, 12)).toBeUndefined(); // double-space gap
    expect(levelAtColumn(row, 54)).toBeUndefined(); // the hint
    expect(levelAtColumn(row, 200)).toBeUndefined();
    expect(levelAtColumn("fold  4 Outline", 7)).toBe(4); // narrow rows work too (plain: no paint brackets)
    expect(levelAtColumn("garbage", 2)).toBeUndefined();
  });
});

describe("KEY", () => {
  test("the row's key is stable", () => {
    expect(KEY).toBe("textfold");
  });
});
