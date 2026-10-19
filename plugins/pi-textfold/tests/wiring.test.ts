import { beforeEach, describe, expect, test, vi } from "vitest";
import { mkdirSync, readFileSync, writeFileSync as fsWriteFileSync } from "node:fs";
import { ENTRY_TYPE } from "../extension/persist";

const writeFileSync = (p: string, s: string) => fsWriteFileSync(p, s);

/** Shape of the calibration overlay component the factory hands back. */
type TeachComponent = { render: (width: number) => string[]; handleInput: (data: string) => boolean };

const readMaybe = (p: string): string | undefined => {
	try {
		return readFileSync(p, "utf8");
	} catch {
		return undefined;
	}
};


beforeEach(() => {
	vi.resetModules();
	// Default the keys file into a per-process tmp dir. Tests that fire session_start
	// without setting the override would otherwise write the welcome marker to the
	// real home; tests that need their own file set it themselves afterwards.
	process.env.TEXTFOLD_PI_KEYS_FILE = `/tmp/textfold-wiring-${process.pid}/keys.json`;
});

type TestTheme = { fg: (_kind: string, s: string) => string; bold: (s: string) => string; dim: (s: string) => string };
type WidgetFactory = (tui: unknown, theme: TestTheme) => {
	render: (width: number) => string[];
};

// A fake pi with the surface the ported index.ts uses, recording everything it does.
function makePi(opts: { branch?: unknown[]; appendEntryThrows?: boolean; digitsFlag?: boolean; editorText?: string } = {}) {
	const handlers = new Map<string, (event: any, ctx: any) => unknown>();
	const shortcuts = new Map<string, { description: string; handler: (ctx: any) => void }>();
	const commands = new Map<string, { handler: (arg: string | undefined, ctx: any) => void }>();
	const entries: { type: string; payload: unknown }[] = [];
	const notifications: string[] = [];
	const widgets = new Map<string, { factory?: WidgetFactory; content?: string[]; opts?: unknown }>();
	const customCaptures: ((tui: unknown, theme: unknown, kb: unknown, done: () => void) => unknown)[] = [];
	let customDone: (() => void) | undefined;
	const calls: string[] = [];
	let editorText = opts.editorText ?? "";
	const editorWrites: string[] = [];

	const branch = opts.branch as unknown[];
	const theme: TestTheme = { fg: (_kind: string, s: string) => s, bold: (s: string) => s, dim: (s: string) => s };
	const screen = {
		invalidate: () => {
			calls.push("invalidate");
		},
		requestRender: (hint: boolean) => {
			calls.push(`render:${hint ? "full" : "normal"}`);
		},
	};

	const pi = {
		on: (name: string, handler: (event: any, ctx: any) => unknown) => {
			handlers.set(name, handler);
			calls.push(`on:${name}`);
		},
		registerShortcut: (key: string, shortcut: { description: string; handler: (ctx: any) => void }) => {
			shortcuts.set(key, shortcut);
			calls.push(`shortcut:${key}`);
		},
		registerCommand: (name: string, command: { handler: (arg: string | undefined, ctx: any) => void }) => {
			commands.set(name, command);
			calls.push(`command:${name}`);
		},
		registerMarkdownTransformer: () => {
			calls.push("markdownTransformer");
		},
		registerFlag: (name: string, flag: { type: string; default?: unknown; description?: string }) => {
			calls.push(`flag:${name}=${String(flag.default)}`);
		},
		getFlag: (name: string) => (name === "textfold-digits" ? opts.digitsFlag === true : undefined),
		appendEntry: (type: string, payload: unknown) => {
			if (opts.appendEntryThrows) throw new Error("disk full");
			entries.push({ type, payload });
			return true;
		},
	};
	const ctx = {
		mode: "tui",
		hasUI: true,
		screen,
		reloads: 0,
		// Command contexts get reload(); the calibration uses it to make the taught
		// keys dispatch in the SAME session (pi snapshots shortcuts at editor setup).
		reload: async () => {
			ctx.reloads++;
		},
		sessionManager: { getBranch: () => branch },
		ui: {
			notify: (message: string, _kind?: string) => notifications.push(message),
			custom: (factory: (tui: unknown, theme: unknown, kb: unknown, done: () => void) => unknown) => {
				customCaptures.push(factory);
				return new Promise<void>((resolve) => {
					customDone = resolve;
				});
			},
			getEditorText: () => editorText,
			setEditorText: (t: string) => {
				editorText = t;
				editorWrites.push(t);
			},
			setWidget: (key: string, build: unknown, placement?: unknown) => {
				const w: { factory?: WidgetFactory; content?: string[]; opts?: unknown } = { opts: placement };
				if (typeof build === "function") w.factory = build as WidgetFactory;
				else w.content = build as string[];
				widgets.set(key, w);
			},
		},
	};

	// Render one widget through its factory, the way the TUI would.
	const render = (key: string, width = 78): string[] => {
		const w = widgets.get(key);
		if (!w) throw new Error(`no widget ${key}`);
		if (w.factory) return w.factory(screen, theme).render(width);
		return w.content ?? [];
	};

	return {
		pi: pi as never,
		customCaptures,
		closeCustom: () => customDone?.(),
		handler: (name: string) => {
			const h = handlers.get(name);
			if (!h) throw new Error(`no ${name} handler registered`);
			return h;
		},
		press: (key: string) => shortcuts.get(key)?.handler(ctx as never),
		runCommand: async (name: string, arg?: string) => commands.get(name)?.handler(arg, ctx as never),
		widgets,
		render,
		notifications,
		calls,
		entries,
		ctx: ctx as never,
		screen,
		editorWrites,
	};
	// The factory-based capture path needs resolve on done: kept where the tests use it.
}

const custom = (level: number, id = "e1") =>
	({ type: "custom", customType: ENTRY_TYPE, data: { level }, id, parentId: "p", timestamp: "2026-10-19T13:46:18.406Z" } as unknown);

const load = async (): Promise<(pi: unknown) => void> => {
	const m = await import("../extension/index.ts");
	const d = (m as unknown as { default: (pi: unknown) => void }).default;
	if (typeof d !== "function") throw new Error("index.ts must default-export its factory");
	return d;
};

describe("a restart restores the level the branch ended on", () => {
	test("a branch ending at level 4: the row marks it, a notify says so, and nothing is written", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [custom(4)] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.entries).toEqual([]); // restore writes nothing
		expect(mk.notifications.join(" ")).toContain("restored");
		expect(mk.render("textfold").join(" ")).toContain("4 Outline"); // the row marks the level read at
	});

	// Per-process dir: the welcome marker persists on disk, so fixed paths would leak
	// "already welcomed" from one run into the next.
	const wt = (n: string) => `/tmp/textfold-wiring-${process.pid}/${n}/keys.json`;

	test("a fresh session starts at Full: one welcome notice, no entry, no re-render", async () => {
		// Behavior change, deliberate: a fresh session used to stay silent. Silence is
		// what strands users whose terminal eats Alt+numbers, so the first session
		// now says once how to check the keys and where to teach them.
		process.env.TEXTFOLD_PI_KEYS_FILE = wt("fresh");
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.entries).toEqual([]);
		expect(mk.notifications).toHaveLength(1);
		expect(mk.notifications.join(" ")).toContain("/fold calibrate");
		expect(mk.render("textfold").join(" ")).toContain("1 Full");
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("the welcome fires once: a second session_start stays silent", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = wt("once");
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.notifications).toHaveLength(1);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		mk.handler("session_start")({ reason: "resume" }, mk.ctx);
		expect(mk.notifications).toHaveLength(1); // the marker, not the reason, decides
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("no welcome when keys are taught or the branch already folds", async () => {
		// Taught keys: the user proved their keyboard works.
		process.env.TEXTFOLD_PI_KEYS_FILE = wt("taught");
		mkdirSync(`/tmp/textfold-wiring-${process.pid}/taught`, { recursive: true });
		writeFileSync(wt("taught"), JSON.stringify({ "1": "alt+&" }));
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.notifications).toEqual([]);
		// A branch that already folds: the user manages without the pointer.
		process.env.TEXTFOLD_PI_KEYS_FILE = wt("folded");
		const mk2 = makePi({ branch: [custom(3)] });
		textfold(mk2.pi);
		mk2.handler("session_start")({ reason: "startup" }, mk2.ctx);
		expect(mk2.notifications.join(" ")).toContain("restored");
		expect(mk2.notifications.join(" ")).not.toContain("calibrate");
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("a resume logs with any reason and restores just the same", async () => {
		const textfold = await load();
		for (const reason of ["startup", "resume", "fork", "new"]) {
			const mk = makePi({ branch: [custom(5, `s-${reason}`)] });
			textfold(mk.pi);
			mk.handler("session_start")({ reason }, mk.ctx);
			mk.press("alt+1"); // a real change (5 → 1) proves the restore took
			mk.press("alt+1"); // a no-op proves dedupe after the restore too
			expect(mk.entries).toEqual([{ type: ENTRY_TYPE, payload: { level: 1 } }]);
		}
	});

	test("a corrupt recent entry does not shadow an earlier valid one", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [custom(2, "a"), { type: "custom", customType: ENTRY_TYPE, data: { level: 99 } }] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.render("textfold").join(" ")).toContain("2 Brief");
	});
});

describe("a level change writes one entry, at most once per change", () => {
	test("repeated presses write nothing; each real change writes one entry", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.press("alt+3");
		mk.press("alt+3");
		mk.press("alt+4");
		expect(mk.entries).toEqual([
			{ type: ENTRY_TYPE, payload: { level: 3 } },
			{ type: ENTRY_TYPE, payload: { level: 4 } },
		]);
	});

	test("appendEntry failing (a full disk) does not strand the extension: the level still changes and the reader still sees it", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [], appendEntryThrows: true });
		textfold(mk.pi);
		expect(() => mk.press("alt+5")).not.toThrow();
		expect(mk.notifications.join(" ")).toContain("Gist");
		expect(mk.entries).toEqual([]);
	});
});

describe("the fold command", () => {
	test("`/fold 4` moves the level like a keypress does, once per change", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.runCommand("fold", "4");
		mk.runCommand("fold", "4");
		expect(mk.entries).toEqual([{ type: ENTRY_TYPE, payload: { level: 4 } }]);
	});

	test("`/fold off` goes back to Full and writes that", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.runCommand("fold", "3");
		mk.runCommand("fold", "off");
		expect(mk.entries.map((e) => e.payload)).toEqual([{ level: 3 }, { level: 1 }]);
	});
});

describe("--textfold-digits registers plain digits from session_start, not the factory", () => {
	test("the flag is registered at the factory; no digit shortcuts before session_start", async () => {
		const textfold = await load();
		const mk = makePi({ digitsFlag: true });
		textfold(mk.pi);
		expect(mk.calls).toContain("flag:textfold-digits=false");
		expect(mk.calls).not.toContain("shortcut:3"); // factory time: the flag is not yet committed
		expect(mk.calls).toContain("shortcut:alt+3");
	});

	test("session_start with the flag on registers 1..5 once", async () => {
		const textfold = await load();
		const mk = makePi({ digitsFlag: true });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		for (const n of [1, 2, 3, 4, 5]) expect(mk.calls).toContain(`shortcut:${n}`);
		mk.handler("session_start")({ reason: "resume" }, mk.ctx); // idempotent across sessions
		expect(mk.calls.filter((c) => c === "shortcut:3")).toHaveLength(1);
	});

	test("session_start with the flag off registers no digits; alt keys untouched", async () => {
		const textfold = await load();
		const mk = makePi({ digitsFlag: false });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.calls).not.toContain("shortcut:3");
		expect(mk.calls).toContain("shortcut:alt+3");
	});

	test("a digit on an empty editor folds to its level; a digit in a draft reinserts itself", async () => {
		const textfold = await load();
		const mk = makePi({ digitsFlag: true, editorText: "" });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		mk.press("3");
		expect(mk.entries).toEqual([{ type: ENTRY_TYPE, payload: { level: 3 } }]);
		expect(mk.notifications.join(" ")).toContain("Points");

		const draft = makePi({ digitsFlag: true, editorText: "ab " });
		textfold(draft.pi);
		draft.handler("session_start")({ reason: "startup" }, draft.ctx);
		draft.press("3");
		expect(draft.editorWrites).toEqual(["ab 3"]);
		expect(draft.entries).toEqual([]); // no fold while typing
	});
});

describe("the preview panel shows the fold before any reply and with it", () => {
	const reply = "## Head one\n\n" + "This is a longish paragraph whose point comes first when folded. ".repeat(4);

	test("the panel is installed at session start: header for the level read at, and an ellipsis for no reply yet", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		const lines = mk.render("textfold-preview");
		expect(lines[0]).toContain("TextFold · Full");
		expect(lines.join(" ")).toContain("…");
	});

	test("an assistant reply refreshes the panel content: the fold, not just the header", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		mk.handler("message_end")({ message: { role: "assistant", content: [{ type: "text", text: reply }] } }, mk.ctx);
		mk.press("alt+3");
		const lines = mk.render("textfold-preview");
		expect(lines[0]).toContain("TextFold · Points");
		expect(lines.join(" ")).toContain("Head one"); // real fold content, not the ellipsis
		expect(lines).not.toContain("…");
	});

	test("the row and the panel are distinct widgets, both present after a session start", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.widgets.has("textfold")).toBe(true);
		expect(mk.widgets.has("textfold-preview")).toBe(true);
		expect(mk.render("textfold").join(" ")).toContain("1 Full");
	});
});

describe("keys you teach once, for any keyboard", () => {
	const writeKeys = (map: Record<string, string>) => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "/tmp/textfold-wiring-test-keys.json";
		writeFileSync("/tmp/textfold-wiring-test-keys.json", JSON.stringify(map));
	};

	test("a fresh extension registers alt+1..5 and nothing else", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "/tmp/textfold-wiring-test-unset.json";
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		for (const n of [1, 2, 3, 4, 5]) expect(mk.calls).toContain(`shortcut:alt+${n}`);
		expect(mk.calls).not.toContain("shortcut:alt+&");
	});

	test("learned keys register alongside, from session start, for any keyboard", async () => {
		writeKeys({ "1": "alt+&", "5": "alt+(" });
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		for (const id of ["shortcut:alt+&", "shortcut:alt+(", "shortcut:alt+1", "shortcut:alt+5"])
			expect(mk.calls).toContain(id);
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("a learned key folds like its digit: alt+& is Full, alt+( is Gist", async () => {
		writeKeys({ "1": "alt+&", "5": "alt+(" });
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.press("alt+&"); // Gist's neighbor... Full from the start: a no-op
		expect(mk.entries).toEqual([]);
		mk.press("alt+5");
		mk.press("alt+&");
		mk.press("alt+(");
		expect(mk.entries).toEqual([
			{ type: ENTRY_TYPE, payload: { level: 5 } },
			{ type: ENTRY_TYPE, payload: { level: 1 } },
			{ type: ENTRY_TYPE, payload: { level: 5 } },
		]);
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("/fold calibrate teaches the keys from the user's own presses and saves them", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "/tmp/textfold-wiring-test-cal.json";
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		const running = mk.runCommand("fold", "calibrate");
		const factory = mk.customCaptures[0];
		expect(factory).toBeDefined();
		// pi-tui hands the factory its own done(); the fake's promise resolves through it.
		const comp = factory({}, {}, {}, () => mk.closeCustom()) as unknown as TeachComponent;
		// The five presses in order: teach, then defaults where the user cannot produce
		// one (a plain digit = keep the default).
		comp.handleInput("\x1b&");
		comp.handleInput("2"); // skip: default stays
		comp.handleInput("\x1b'");
		comp.handleInput("\x1b4");
		comp.handleInput("\x1b(");
		await running;
		expect((mk.ctx as unknown as { reloads: number }).reloads).toBe(1); // teaching must be live in this same session too
		expect(mk.notifications.join(" ")).toContain("Saved");
		const map = JSON.parse(readFileSync("/tmp/textfold-wiring-test-cal.json", "utf8"));
		expect(map).toEqual({ "1": "alt+&", "2": "alt+2", "3": "alt+'", "4": "alt+4", "5": "alt+(" });
		expect(mk.calls).toContain("shortcut:alt+&"); // re-registered right after teaching
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("/fold calibrate on escape teaches nothing and saves nothing", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "/tmp/textfold-wiring-test-cancel.json";
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		const running = mk.runCommand("fold", "calibrate");
		const comp = mk.customCaptures[0]({}, {}, {}, () => mk.closeCustom()) as unknown as TeachComponent;
		comp.handleInput("\x1b&");
		comp.handleInput("\x1b"); // escape
		await running;
		expect(readMaybe("/tmp/textfold-wiring-test-cancel.json")).toBeUndefined();
		expect((mk.ctx as unknown as { reloads?: number }).reloads ?? 0).toBe(0); // quitting teaches nothing live
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});

	test("/fold keys says what is bound", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "/tmp/textfold-wiring-test-keys.json"; // written above
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		await mk.runCommand("fold", "keys");
		expect(mk.notifications.join(" ")).toContain("alt+&");
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
	});
});

describe("what the extension registers", () => {
	test("alt keys, the fold command, the transformer, and the two handlers", async () => {
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		for (const n of [1, 2, 3, 4, 5]) expect(mk.calls).toContain(`shortcut:alt+${n}`);
		expect(mk.calls).toContain("command:fold");
		expect(mk.calls).toContain("markdownTransformer");
		expect(mk.calls).toContain("on:session_start");
		expect(mk.calls).toContain("on:before_agent_start");
	});

	test("a before_agent_start adds the fold style as a section, leaving the other options", async () => {
		const textfold = await load();
		const mk = makePi();
		textfold(mk.pi);
		const event = { systemPromptOptions: { sections: { keepme: "kept" }, model: "x" } };
		const out = mk.handler("before_agent_start")(event, mk.ctx);
		expect((event.systemPromptOptions.sections as Record<string, string>).textfold).toContain("can fold your replies");
		expect((event.systemPromptOptions.sections as Record<string, string>).keepme).toBe("kept");
		expect(event.systemPromptOptions.model).toBe("x");
		expect(out).toEqual({});
	});
});
