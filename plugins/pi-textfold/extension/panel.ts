/**
 * The fold-preview panel for Pi's textfold extension.
 *
 * Pure helpers, so the tests can cover them without running Pi. The panel keeps the latest
 * reply's fold in view even after the reply has scrolled out of the transcript: a level
 * change redraws the transcript through `screen.invalidate()` (every reply re-folds, proven
 * on pi 1.3.0 with two replies), but the transcript scrolls, and a reader who just pressed
 * Alt+3 wants the folded reply where they are looking. It is the second widget (the row
 * above the prompt being the first), and it shows the restored level before any reply.
 */
import { fold, LEVELS, worthFolding } from "./fold";
import { hintForKeys, type Level } from "./level";

export const PANEL_KEY = "textfold-preview";

/** The lines of the preview panel for `markdown` folded to `level`: header, blank, folded
 *  text. An empty `markdown` still renders the header (with a placeholder), so a resumed
 *  session shows the restored level before any reply arrives. */
export function foldPanelLines(markdown: string, level: number, width = 78, keys?: Record<string, string>): string[] {
	if (level < 1 || level > 5) return [];
	const hint = `(${hintForKeys(keys).replace("…", "..")} / /fold N)`;
	if (!markdown) return [`TextFold · ${LEVELS[level - 1]} ${hint}`, "", "…"];
	const f = fold(markdown, level);
	const shown = worthFolding(markdown, f.text) ? f.text : markdown;
	return [`TextFold · ${LEVELS[level - 1]} ${hint}`, "", ...wrapText(shown || "…", width)];
}

/** Word-wrap plain text (the fold writes no ANSI) to at most `width` columns,
 *  hard-breaking any single token wider than `width`. */
export function wrapText(text: string, width = 78): string[] {
	return text.split("\n").flatMap((line) => {
		if (line.length <= width) return [line];
		const out: string[] = [];
		let buf: string = "";
		for (const word of line.split(" ")) {
			for (let rest = word.length > width ? word : ""; rest; ) {	// a token wider than the line: hard-break it
				if (buf) { out.push(buf); buf = ""; }
				if (rest.length > width) {
					out.push(rest.slice(0, width));
					rest = rest.slice(width);
				} else {
					buf = rest;	// the tail joins the normal flow
					rest = "";
				}
			}
			const next = buf ? `${buf} ${word}` : word;
			if (next.length > width && buf) {
				out.push(buf);
				buf = word;
			} else buf = next;
		}
		if (buf) out.push(buf);
		return out;
	});
}

export type { Level };
