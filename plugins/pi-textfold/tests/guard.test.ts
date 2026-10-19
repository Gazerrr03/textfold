/**
 * Digit-guard decision tests. `guardDigit` is pure: give it the editor text,
 * the typed digit, and whether the flag is on; get back what should happen.
 * The shortcut registration itself is gated at load time, so "off" means no
 * digit shortcuts exist at all — this test pins the off decision anyway.
 */
import { describe, expect, test } from "vitest";
import { guardDigit } from "../extension/guard.js";

describe("guardDigit", () => {
	test("empty prompt: digit is a level change", () => {
		expect(guardDigit({ editorText: "", digit: "3", digitsEnabled: true })).toEqual({ kind: "level", level: 3 });
	});

	test("whitespace-only prompt counts as empty", () => {
		expect(guardDigit({ editorText: "  \t ", digit: "5", digitsEnabled: true })).toEqual({ kind: "level", level: 5 });
	});

	test("digits typed into draft text reinsert instead", () => {
		expect(guardDigit({ editorText: "ab ", digit: "4", digitsEnabled: true })).toEqual({ kind: "reinsert" });
	});

	test("any digit at a non-empty prompt reinserts", () => {
		expect(guardDigit({ editorText: "fix #", digit: "1", digitsEnabled: true })).toEqual({ kind: "reinsert" });
	});

	test("flag off is a no-op", () => {
		expect(guardDigit({ editorText: "", digit: "3", digitsEnabled: false })).toEqual({ kind: "off" });
		expect(guardDigit({ editorText: "ab", digit: "3", digitsEnabled: false })).toEqual({ kind: "off" });
	});
});
