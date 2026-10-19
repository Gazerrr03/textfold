/**
 * The level replies are read at, and the /fold parser, for Pi's textfold extension.
 *
 * Pure helpers, so the tests can cover them without running Pi.
 */
import { LEVELS } from "./fold";

export type Level = 1 | 2 | 3 | 4 | 5;

/** The key of the level row above the prompt. */
export const KEY = "textfold";

/** How the row is coloured: its label and hint, the level read at, the others. */
export type Paint = { label: (s: string) => string; current: (s: string) => string; other: (s: string) => string };

/**
 * The hint names the actual bindings: the taught glyphs' range when levels 1
 * and 5 were both taught (`Alt+&…(`), the default otherwise. A partial teaching
 * falls back to the default rather than naming half a keyboard.
 */
export function hintForKeys(keys?: Record<string, string>): string {
	const glyph = (id: string | undefined): string | undefined => {
		if (typeof id !== "string") return undefined;
		const m = /^alt\+(\S+)$/i.exec(id);
		return m ? m[1] : undefined;
	};
	const first = glyph(keys?.["1"]);
	const last = glyph(keys?.["5"]);
	return first && last ? `Alt+${first}…${last}` : "Alt+1…5";
}

/**
 * Which level a click at visible column `x` of the plain row names, if any.
 * The row is `fold` + five level segments in order, joined on double spaces,
 * with an optional hint after them: only a column inside a level segment
 * counts, so label, gaps, and hint clicks never misfire to a neighbor.
 */
export function levelAtColumn(row: string, x: number): Level | undefined {
	// Full rows join on double spaces; narrow rows use one ("fold 4 Outline").
	const m = /^fold +/.exec(row);
	if (!m || x < m[0].length) return undefined;
	let i = m[0].length;
	for (const chunk of row.slice(i).split("  ")) {
		const hit = /^[1-5] /.exec(chunk);
		if (hit && x >= i && x < i + chunk.length) return Number(hit[0][0]) as Level;
		i += chunk.length + 2;
	}
	return undefined;
}

/**
 * The row above the prompt: the five levels with their keys, the one read at marked, as Claude Code's mod
 * shows them. Where it is too narrow the hint goes first, then every level but the one read at.
 */
export function levelRow(level: Level, width: number, paint: Paint, keys?: Record<string, string>): string {
	const row = (p: Paint, hint: boolean) =>
		[p.label("fold"), ...LEVELS.map((name, i) => (i + 1 === level ? p.current : p.other)(`${i + 1} ${name}`)), ...(hint ? [p.label(`· ${hintForKeys(keys)}`)] : [])].join("  ");
	const plain: Paint = { label: (s) => s, current: (s) => s, other: (s) => s };
	for (const hint of [true, false]) if (row(plain, hint).length <= width) return row(paint, hint);
	return `${paint.label("fold")} ${paint.current(`${level} ${LEVELS[level - 1]}`)}`;
}

/**
 * `/fold <args>`: "", "off" and a name from LEVELS cycle or pick a level; an
 * integer 1..5 picks it; anything else is reported and the level is kept.
 */
export function parseLevelArg(arg: string, current: Level): { level?: Level; error?: string } {
	const text = arg.trim();
	if (!text) return { level: ((current % 5) + 1) as Level };
	if (text === "off" || text.toLowerCase() === "full") return { level: 1 };
	const byName = LEVELS.findIndex((name) => name.toLowerCase() === text.toLowerCase());
	if (byName >= 0) return { level: (byName + 1) as Level };
	const num = Number(text);
	if (Number.isInteger(num) && num >= 1 && num <= 5) return { level: num as Level };
	return { error: `Unknown fold level: ${text}` };
}
