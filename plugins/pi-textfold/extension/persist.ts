/** Fold-level persistence: what the session stores and what a session start
 *  restores. pi stores customs as `{type:"custom", customType, data}`; the
 *  restore scans one branch (getBranch, which excludes abandoned branches),
 *  last match wins. */
export const ENTRY_TYPE = "textfold-level";

/** The data payload for `pi.appendEntry(ENTRY_TYPE, levelEntryDraft(n))`. */
export function levelEntryDraft(level: number): { level: number } {
	return { level: level as 1 | 2 | 3 | 4 | 5 };
}

/** The level the branch ends on, or undefined: unrelated fields and data are
 *  ignored, and an out-of-range (corrupt) recent entry does not shadow an
 *  earlier valid one, so restore falls back to it instead of failing. */
export function restoredLevel(branchEntries: readonly unknown[] | undefined | null): 1 | 2 | 3 | 4 | 5 | undefined {
	if (!Array.isArray(branchEntries)) return undefined;
	for (let i = branchEntries.length - 1; i >= 0; i--) {
		const e = branchEntries[i] as { type?: string; customType?: string; data?: { level?: unknown } } | undefined;
		if (!e || e.type !== "custom" || e.customType !== ENTRY_TYPE) continue;
		const n = e.data?.level;
		if (typeof n === "number" && Number.isInteger(n) && n >= 1 && n <= 5) return n as 1 | 2 | 3 | 4 | 5;
	}
	return undefined;
}
