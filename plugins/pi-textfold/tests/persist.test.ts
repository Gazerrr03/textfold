import { describe, expect, test } from "vitest";

import { ENTRY_TYPE, levelEntryDraft, restoredLevel } from "../extension/persist";

// Fixture entries shaped exactly like pi's persisted session entries
// (capture from /tmp/designprobe: getBranch at 13:51:41).
const entry = (customType: string, data: unknown, id: string) =>
  ({ type: "custom", customType, data, id, parentId: "1963fd1f",
     timestamp: "2026-10-15T13:46:18.406Z" as const });

const BRANCH = [
  { type: "model_change", data: {} } as unknown as Record<string, unknown>,
  { type: "thinking_level_change", data: {} } as unknown as Record<string, unknown>,
  entry(ENTRY_TYPE, { level: 3 }, "fa156328"),
  { type: "message", data: {} } as unknown as Record<string, unknown>,
  { type: "message", data: {} } as unknown as Record<string, unknown>,
];

describe("levelEntryDraft", () => {
  test("a draft pi accepts for appendEntry carries the level", () => {
    expect(levelEntryDraft(3)).toEqual({ level: 3 });
  });
});

describe("restoredLevel", () => {
  test("the last textfold-level entry on the branch wins", () => {
    const b: any[] = [...BRANCH, entry(ENTRY_TYPE, { level: 5 }, "ffff001")];
    expect(restoredLevel(b)).toBe(5);
    expect(restoredLevel(BRANCH as any)).toBe(3);
  });

  test("foreign customTypes and other entry kinds are ignored", () => {
    const b: any[] = [entry("other-plugin", { level: 9 }, "aaaa001"), ...BRANCH];
    expect(restoredLevel(b)).toBe(3);
  });

  test("an out-of-range recent entry does not shadow an earlier valid one", () => {
    const b: any[] = [...BRANCH, entry(ENTRY_TYPE, { level: 9 }, "ffff001")];
    expect(restoredLevel(b)).toBe(3);
    expect(restoredLevel([entry(ENTRY_TYPE, { level: 9 }, "ffff001") as any])).toBeUndefined();
  });

  test("no entries, or none of ours, means nothing to restore", () => {
    expect(restoredLevel([])).toBeUndefined();
    const b: any[] = [entry("other-plugin", { level: 9 }, "aaaa001")];
    expect(restoredLevel(b)).toBeUndefined();
    expect(restoredLevel(undefined as never)).toBeUndefined();
  });
});

describe("ENTRY_TYPE", () => {
  test("the entry type is stable", () => {
    expect(ENTRY_TYPE).toBe("textfold-level");
  });
});
