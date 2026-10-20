/** The keys you teach once, on any keyboard.
 *  Pi matches shortcuts by the bytes the terminal SENDS for a key: on most ISO
 *  layouts Alt+row produces ESC + the unshifted glyph (`&` on AZERTY's 1), so the
 *  plain `alt+1..5` binds only on US/direct layouts. Rather than a table of
 *  layouts, `/fold calibrate` teaches the extension the five keys from the
 *  user's own presses; this module stores and re-reads that learning.
 *
 *  The file lives in the agent dir next to the settings (a documented per-user
 *  place, no daemon, no account). Rows are validated on load: levels 1..5 only,
 *  values must look like pi key ids ("alt+..."), malformed rows are dropped. */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

export type KeysMap = Record<string, string>;

/** Where the taught keys live. TEXTFOLD_PI_KEYS_FILE overrides — mostly so the
 *  harness and the tests can point elsewhere (never at the user's file). */
export function keysFile(): string {
	// Empty counts as unset: the suite clears the override with "", and dirname("")
	// is "." — which once wrote a marker into the repo. Never a relative path.
	const override = process.env["TEXTFOLD_PI_KEYS_FILE"] || undefined;
	return override ?? join(homedir(), ".pi", "agent", "textfold-keys.json");
}

/** Levels 1..5 only; values must look like a pi key id; anything malformed
 *  and out of range is dropped rather than trusted. */
export function sanitizeKeys(raw: unknown): KeysMap {
	const out: Record<string, string> = {};
	if (!raw || typeof raw !== "object") return out;
	for (const level of [1, 2, 3, 4, 5]) {
		const value = (raw as Record<string, unknown>)[String(level)];
		if (typeof value === "string" && /^alt\S+$/.test(value)) out[String(level)] = value;
	}
	return out;
}

/** The first-run pointer lives next to the keys file, so the test override
 *  redirects it too and the suite never touches the user's home. */
export function welcomeFile(file = keysFile()): string {
	return join(dirname(file), "textfold-welcomed");
}

/** False when the marker is missing OR unreadable: doubt means "not welcomed". */
export function hasBeenWelcomed(file = welcomeFile()): boolean {
	try {
		return existsSync(file);
	} catch {
		return false;
	}
}

/** One silent write; an unwritable home must never break a session start. */
export function markWelcomed(file = welcomeFile()): void {
	try {
		mkdirSync(dirname(file), { recursive: true });
		writeFileSync(file, new Date().toISOString() + "\n");
	} catch {
		// a read-only home simply gets the pointer again next time
	}
}

/** undefined means "no learned keys": a missing or unparseable file is not an error. */
export function loadKeys(file = keysFile()): KeysMap | undefined {
	let parsed: unknown;
	try {
		parsed = JSON.parse(readFileSync(file, "utf8"));
	} catch {
		return undefined;
	}
	const clean = sanitizeKeys(parsed);
	return Object.keys(clean).length > 0 ? clean : undefined;
}

export function saveKeys(file: string = keysFile(), map: KeysMap): void {
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, JSON.stringify(map, null, 2) + "\n");
}
