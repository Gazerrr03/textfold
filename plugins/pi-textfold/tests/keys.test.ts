import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mkdirSync, writeFileSync } from "node:fs";

// Per-process dir: the welcome marker persists on disk, so fixed paths would leak
// "already welcomed" from one run into the next.
const TMP = `/tmp/textfold-keys-test-${process.pid}`;

afterEach(() => {
	delete process.env["TEXTFOLD_PI_KEYS_FILE"];
});

beforeEach(() => {
	mkdirSync(TMP, { recursive: true });
});

async function importKeys() {
	return import("../extension/keys.js");
}

describe("the learned keyboard map file", () => {
	test("keysFile() treats an empty override as unset, never a relative path", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = "";
		const keys = await importKeys();
		const f = keys.keysFile();
		expect(f.endsWith("textfold-keys.json")).toBe(true);
		expect(f.startsWith("/")).toBe(true);
	});

	test("keysFile() follows TEXTFOLD_PI_KEYS_FILE when set, and lives in the agent dir otherwise", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = TMP + "/keys.json";
		const keys = await importKeys();
		expect(keys.keysFile()).toBe(TMP + "/keys.json");
		delete process.env.TEXTFOLD_PI_KEYS_FILE;
		expect(keys.keysFile().endsWith("textfold-keys.json")).toBe(true);
	});

	test("saveKeys writes the map through; loadKeys reads it back with malformed rows dropped", async () => {
		const keys = await importKeys();
		keys.saveKeys(TMP + "/keys.json", {
			"1": "alt+&",
			"2": "alt+é", // multi-byte: the pi matcher may not match it, but a store is still wrong to drop
			"3": "not-a-key-id", // malformed: dropped on load
			"9": "alt+9", // not a level: dropped on load
		});
		expect(keys.loadKeys(TMP + "/keys.json")).toEqual({
			"1": "alt+&",
			"2": "alt+é",
		});
	});

	test("loadKeys on a missing file or unparseable file is simply no learned keys", async () => {
		const keys = await importKeys();
		expect(keys.loadKeys(TMP + "/missing.json")).toBeUndefined();
		writeFileSync(TMP + "/broken.json", "{not json");
		expect(keys.loadKeys(TMP + "/broken.json")).toBeUndefined();
	});
});

describe("the first-run welcome marker", () => {
	test("welcomeFile() sits next to the keys file, so tests never touch the user's home", async () => {
		process.env.TEXTFOLD_PI_KEYS_FILE = TMP + "/w/keys.json";
		const keys = await importKeys();
		expect(keys.welcomeFile()).toBe(TMP + "/w/textfold-welcomed");
	});

	test("hasBeenWelcomed is false until markWelcomed writes it", async () => {
		const keys = await importKeys();
		const f = TMP + "/w2/marker";
		expect(keys.hasBeenWelcomed(f)).toBe(false);
		keys.markWelcomed(f);
		expect(keys.hasBeenWelcomed(f)).toBe(true);
	});

	test("markWelcomed swallows an unwritable path instead of throwing", async () => {
		const keys = await importKeys();
		expect(() => keys.markWelcomed("/nonexistent-dir-xyz/marker")).not.toThrow();
		expect(keys.hasBeenWelcomed("/nonexistent-dir-xyz/marker")).toBe(false);
	});
});
