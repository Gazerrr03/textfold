import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mkdirSync, writeFileSync } from "node:fs";

const TMP = "/tmp/textfold-keys-test";

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
