/**
 * TextFold for Pi.
 *
 * A Pi coding-agent extension from TextFold (see `plugins/textfold` for the Claude
 * Code mod this mirrors): every Pi reply folds to the level you need, from every
 * word to the answer in one sentence, with one key. No second model and no
 * summary; the fold keeps prefixes of what the agent wrote.
 *
 * It works because the style section asked for below makes the agent open every
 * paragraph and list item with the sentence that states its point. Folding then
 * keeps a prefix of what Pi wrote; the fold changes the order of what the agent
 * says, not what it says or how much.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

import type { KeyId, TUI } from "@earendil-works/pi-tui";
import { appendFileSync } from "node:fs";
import { fold, LEVELS, worthFolding } from "./fold";
import { guardDigit } from "./guard";
import { foldPanelLines, PANEL_KEY } from "./panel";
import { KEY, levelRow, parseLevelArg, type Level } from "./level";
import { ENTRY_TYPE, levelEntryDraft, restoredLevel } from "./persist";

// Debug tap: writes every shortcut/apply/restore decision when TEXTFOLD_PI_DEBUG
// is set. Zero-cost otherwise.
const DEBUG = process.env.TEXTFOLD_PI_DEBUG
	? (s: string) => {
		const line = new Date().toISOString().slice(11, 19) + " " + s;
		try {
			appendFileSync(process.env.TEXTFOLD_PI_DEBUG_FILE ?? "/tmp/textfold-pi-debug.log", line + "\n");
		} catch {
			// stderr below still exposes it
		}
		try {
			(process as unknown as { stderr?: { write(s: string): void } }).stderr?.write?.(line + "\n");
		} catch {
			// best effort
		}
	}
	: undefined;

// Identical to the Claude Code mod's prompt section, so replies fold the same way
// on every harness. It asks for the point first at every scale.
const STYLE = `# Replies that fold
The person reading this session can fold your replies with one key: to each paragraph's first sentence or two, to the headings, or to the reply's first sentence. Write so that every fold still reads:
- Open the reply with one sentence that answers, or that says what you did.
- Open every paragraph and every list item with a sentence that states its point and reads on its own; reasons, details and caveats come after it.
- Give a reply longer than four paragraphs a few short headings.
This changes the order of what you write, not its content or its length.`;

export default function textfoldFold(pi: ExtensionAPI) {
	pi.registerFlag("textfold-digits", {
		type: "boolean",
		default: false,
		description: "Digits 1..5 fold on an empty prompt and are reinserted while typing",
	});
	// The level every reply is read at: 1 Full (as written) to 5 Gist. Full at start, then
	// restored from the session's branch so a resumed session continues where the reader
	// left off (C1). Restore writes nothing: the level is already on disk.
	let level: Level = 1;
	// The latest settled assistant reply, for the preview panel: it shows the fold of
	// this, at the level in force, re-rendered on every level change (the widget
	// re-renders its content unconditionally, unlike the cached transcript).
	let lastAssistant = "";

	// The style section, appended as a structured prompt section so the session
	// records a delta instead of a replaced prompt.
	pi.on("before_agent_start", (event) => {
		event.systemPromptOptions.sections = {
			...event.systemPromptOptions.sections,
			textfold: STYLE,
		};
		return {};
	});

	// Each reply folded as Pi draws it, on the screen only: what the model sees is never changed.
	pi.registerMarkdownTransformer((markdown, context) => {
		if (context.messageType !== "assistant" || level === 1) return markdown;
		const f = fold(markdown, level);
		if (!worthFolding(markdown, f.text)) return markdown;
		return `${f.text || "…"}\n\n*${levelName(level)} · ${f.shown} of ${f.total} words · Alt+1 unfolds*`;
	});

	// The row above the prompt names the five levels and marks the one read at. Pi hands its screen to the
	// row's factory, which the extension keeps: a new level has to be drawn on all of it.
	let screen: TUI | undefined;
	const install = (ctx: ExtensionContext) =>
		ctx.ui.setWidget(
			KEY,
			(tui, theme) => {
				screen = tui;
				DEBUG?.("row installed");
				const paint = { label: (s: string) => theme.fg("muted", s), current: (s: string) => theme.bold(theme.fg("accent", s)), other: (s: string) => theme.fg("dim", s) };
				return { render: (width: number) => [` ${levelRow(level, width - 1, paint)}`], invalidate: () => {} };
			},
			{ placement: "aboveEditor" },
		);

	// Plain digits exist only behind --textfold-digits, because Pi dispatches extension
	// shortcuts before the editor sees any input. Registration must wait for session
	// start: pi commits CLI flag values after the factory runs, so reading the flag at
	// factory time always yields the default (a real bug this port inherited and fixed).
	let digitKeysRegistered = false;

	// Restore is unconditional on session start: a `--session` resume reports reason
	// "startup", so no reason-based gating can be trusted. The scan takes the branch's
	// last valid textfold entry; corrupt ones are skipped (persist.ts).
	pi.on("session_start", (event, ctx) => {
		if (!digitKeysRegistered) {
			digitKeysRegistered = true;
			if ((typeof (pi as { getFlag?: unknown }).getFlag === "function"
				&& (pi as { getFlag: (n: string) => unknown }).getFlag("textfold-digits") === true)) registerDigitKeys();
		}

		const branch = (ctx?.sessionManager as unknown as { getBranch?: () => unknown[] } | undefined)?.getBranch?.();
		const restored = restoredLevel(branch);
		DEBUG?.(`restore reason=${(event as { reason?: string }).reason} entries=${Array.isArray(branch) ? branch.length : -1} restored=${restored}`);
		if (restored && restored !== level) {
			level = restored as Level;
			ctx?.ui.notify(`TextFold level restored: ${levelName(restored)}`, "info");
		}
		install(ctx);
		ctx?.ui.setWidget(PANEL_KEY, foldPanelLines(lastAssistant, level));
	});

	// A new level folds every reply in place at once, the earlier ones too. Pi keeps each reply as it drew it
	// until its text or the screen's width changes, so what it kept is dropped and the whole screen drawn again.
	// The level is also written to the session (C1): one entry per real change, so a restart
	// resumes where the reader left off. A failed write (a full disk) must not strand the
	// reader: the level still changes on the screen.
	const apply = (next: Level, ctx: ExtensionContext) => {
		if (next === level) return;
		level = next;
		try {
			pi.appendEntry(ENTRY_TYPE, levelEntryDraft(next));
		} catch (e) {
			DEBUG?.(`append failed: ${(e as Error)?.message ?? String(e)}`);
		}
		ctx.ui.notify(`Fold: ${levelName(next)}`, "info");
		ctx.ui.setWidget(PANEL_KEY, foldPanelLines(lastAssistant, level));
		if (!screen) install(ctx);
		screen?.invalidate();
		screen?.requestRender(true);
	};

	// The latest settled assistant reply feeds the preview panel.
	pi.on("message_end", (event, ctx) => {
		const m = event.message as { role?: string; content?: Array<{ type?: string; text?: string }> };
		DEBUG?.(`message_end role=${m?.role} blocks=${Array.isArray(m?.content) ? m.content.length : -1}`);
		if (m?.role !== "assistant" || !Array.isArray(m.content)) return;
		const text = m.content.filter((b) => b?.type === "text" && b.text).map((b) => b.text).join("\n\n");
		if (text) {
			lastAssistant = text;
			ctx?.ui.setWidget(PANEL_KEY, foldPanelLines(lastAssistant, level));
		}
	});

	// Alt+1..Alt+5. Not plain digits: Pi dispatches extension shortcuts before the
	// editor sees any input, so registered 1..5 would swallow typed digits.
	for (const n of [1, 2, 3, 4, 5] as const) {
		const key = `alt+${n}` as KeyId;
		pi.registerShortcut(key, {
			description: `Fold replies to ${levelName(n)}`,
			handler: async (ctx) => apply(n, ctx),
		});
	}

	// --textfold-digits's shortcuts: a digit changes the level when the prompt is
	// empty and reinserts itself anywhere else, so the editor never swallows a pressed
	// digit the shortcut intercepted.
	const registerDigitKeys = () => {
		for (const n of [1, 2, 3, 4, 5] as const) {
			const key = `${n}` as KeyId;
			pi.registerShortcut(key, {
				description: `Fold replies to ${levelName(n)} when the prompt is empty; reinsert the digit otherwise`,
				handler: async (ctx) => {
					const editorText = (typeof ctx?.ui?.getEditorText === "function" ? ctx.ui.getEditorText() : "") ?? "";
					const decision = guardDigit({ editorText, digit: `${n}`, digitsEnabled: true });
					DEBUG?.(`digit ${n} decision=${decision.kind}${decision.kind === "level" ? ` level=${decision.level}` : ""} editorLen=${editorText.length}`);
					if (decision.kind === "level") {
						apply(decision.level, ctx as ExtensionContext);
					} else if (decision.kind === "reinsert" && typeof ctx?.ui?.setEditorText === "function") {
						ctx.ui.setEditorText(editorText + `${n}`);
					}
				},
			});
		}
	};

	pi.registerCommand("fold", {
		description: "Fold replies: 1..5, a level name, off, or nothing for the next level",
		handler: async (arg: string | undefined, ctx) => {
			const got = parseLevelArg(arg ?? "", level);
			if (got.error) {
				ctx.ui.notify(got.error, "warning");
				return;
			}
			if (got.level) apply(got.level, ctx);
		},
	});
}

const levelName = (n: number): string => LEVELS[n - 1] ?? "Full";
