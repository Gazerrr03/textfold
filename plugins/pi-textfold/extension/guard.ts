/**
 * The digit-guard decision (F2): when `--textfold-digits` is on, plain digits
 * 1..5 are extension shortcuts, and pi dispatches them before the editor sees
 * any input (B3). A digit typed into a draft must therefore be reinserted, or
 * it never reaches the text; a digit on an empty prompt changes the fold level.
 * The shortcuts are only registered when the flag is on, so off means the
 * decision is never asked for — the off branch exists to pin that contract.
 */
export type GuardDecision = { kind: "level"; level: 1 | 2 | 3 | 4 | 5 } | { kind: "reinsert" } | { kind: "off" };

export function guardDigit(args: { editorText: string; digit: string; digitsEnabled: boolean }): GuardDecision {
	const { editorText, digit, digitsEnabled } = args;
	if (!digitsEnabled) return { kind: "off" };
	const n = Number(digit);
	if (!Number.isInteger(n) || n < 1 || n > 5) return { kind: "reinsert" };
	if (editorText.trim().length === 0) return { kind: "level", level: n as 1 | 2 | 3 | 4 | 5 };
	return { kind: "reinsert" };
}
