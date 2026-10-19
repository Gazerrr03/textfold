import { describe, expect, test } from "vitest";

import { fold, LEVELS } from "../extension/fold";
import { foldPanelLines, wrapText, PANEL_KEY } from "../extension/panel";

describe("wrapText", () => {
  test("keeps short lines as written", () => {
    expect(wrapText("Already short.\nAlso short.", 78)).toEqual(["Already short.", "Also short."]);
  });

  test("wraps a long line at the width, on spaces, without dropping words", () => {
    const words = Array.from({ length: 40 }, (_, i) => `word${i}`);
    const text = words.join(" ");
    const lines = wrapText(text, 78);
    for (const line of lines) expect(line.length).toBeLessThanOrEqual(78);
    expect(lines.join(" ")).toBe(text);
  });

  test("breaks a word that never fits", () => {
    const lines = wrapText("x".repeat(90), 78);
    expect(lines[0]!.length).toBeLessThanOrEqual(78);
  });
});

describe("foldPanelLines", () => {
  const REPLY = Array.from({ length: 12 }, (_, i) => `Sentence ${i} has a few words in it.`).join(" ");  test("a Full panel shows the reply as written; an empty markdown shows just the header+placeholder", () => {
    // The port keeps the panel as a persistent second widget, so at Full it shows the
    // reply with its own header instead of hiding (the row marks the level too).
    const lines = foldPanelLines(REPLY, 1);
    expect(lines[0]).toBe("TextFold · Full (Alt+1..5 / /fold N)");
    expect(lines.join(" ")).toContain(REPLY.slice(0, 40));
    expect(foldPanelLines("", 3)).toEqual([
      "TextFold · Points (Alt+1..5 / /fold N)",
      "",
      "…",
    ]);
  });

  test("the panel names the level and shows the folded prefix", () => {
    const lines = foldPanelLines(REPLY, 3);
    expect(lines[0]).toBe(`TextFold · ${"Points"} (Alt+1..5 / /fold N)`);
    const body = lines.slice(2).join("\n");
    expect(body.length).toBeLessThan(REPLY.length);
    // prefix-preserving: the panel only loses what a fold at this level loses
    const f = fold(REPLY, 3);
    expect(body.startsWith(f.text.split("\n")[0])).toBe(true);
  });

  test("a short reply shows whole rather than folded", () => {
    const short = "Just one line.";
    expect(foldPanelLines(short, 3).join(" ")).toContain(short);
  });

  test("taught keys name the panel's hint the way the row's does", () => {
    const taught = { "1": "alt+&", "2": "alt+2", "3": "alt+'", "4": "alt+4", "5": "alt+(" };
    expect(foldPanelLines("", 3, 78, taught)[0]).toBe("TextFold · Points (Alt+&..( / /fold N)");
    expect(foldPanelLines(REPLY, 1, 78, taught)[0]).toBe("TextFold · Full (Alt+&..( / /fold N)");
  });
});

describe("PANEL_KEY", () => {
  test("the panel's widget key is distinct from the row's (upstream owns 'textfold') and stable", () => {
    expect(PANEL_KEY).toBe("textfold-preview");
  });
});
