import { beforeEach, describe, expect, test, vi } from "vitest";

import { ENTRY_TYPE } from "../extension/persist";

beforeEach(() => {
	vi.resetModules();
});

type TestTheme = { fg: (_kind: string, s: string) => string; bold: (s: string) => string; dim: (s: string) => string };
type WidgetFactory = (tui: unknown, theme: TestTheme) => {
	render: (width: number) => string[];
};

// A fake pi with the surface the ported index.ts uses, recording everything it does.
function makePi(opts: { branch?: unknown[]; appendEntryThrows?: boolean } = {}) {
	const handlers = new Map<string, (event: any, ctx: any) => unknown>();
	const shortcuts = new Map<string, { description: string; handler: (ctx: any) => void }>();
	const commands = new Map<string, { handler: (arg: string | undefined, ctx: any) => void }>();
	const entries: { type: string; payload: unknown }[] = [];
	const notifications: string[] = [];
	const widgets = new Map<string, { factory?: WidgetFactory; content?: string[]; opts?: unknown }>();
	const calls: string[] = [];

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
		appendEntry: (type: string, payload: unknown) => {
			if (opts.appendEntryThrows) throw new Error("disk full");
			entries.push({ type, payload });
			return true;
		},
	};
	const ctx = {
		screen,
		sessionManager: { getBranch: () => branch },
		ui: {
			notify: (message: string, _kind?: string) => notifications.push(message),
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
		handler: (name: string) => {
			const h = handlers.get(name);
			if (!h) throw new Error(`no ${name} handler registered`);
			return h;
		},
		press: (key: string) => shortcuts.get(key)?.handler(ctx as never),
		runCommand: (name: string, arg?: string) => commands.get(name)?.handler(arg, ctx as never),
		widgets,
		render,
		notifications,
		calls,
		entries,
		ctx: ctx as never,
		screen,
	};
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

	test("a fresh session starts at Full: no notify, no entry, no re-render", async () => {
		const textfold = await load();
		const mk = makePi({ branch: [] });
		textfold(mk.pi);
		mk.handler("session_start")({ reason: "startup" }, mk.ctx);
		expect(mk.entries).toEqual([]);
		expect(mk.notifications).toEqual([]);
		expect(mk.render("textfold").join(" ")).toContain("1 Full");
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
