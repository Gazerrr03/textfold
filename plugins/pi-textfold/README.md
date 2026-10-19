# TextFold for Pi

Your agent writes more than you have time to read. TextFold folds every reply in [Pi](https://pi.dev) to the level you need, from every word to the answer in one sentence, with one key. It is the fold of [TextFold for Claude Code](../textfold/README.md), as a Pi extension, from [TextFold](../../README.md).

<img src="../../docs/assets/pi.gif" width="880" alt="A reply in Pi folding a level at a time, from the full text down to its answer in one sentence, one key each">

| Key | Level | What you get |
|:-:|---|---|
| **Alt+1** | **Full** | every word the model wrote |
| **Alt+2** | **Brief** | each point, with the reason behind it |
| **Alt+3** | **Points** | just the points, at a glance |
| **Alt+4** | **Outline** | the map of a long reply: its sections, and what each one says |
| **Alt+5** | **Gist** | the answer, in one sentence |

Hold Alt and type the digit, or type `/fold` and a level: `/fold 3`, `/fold points`, `/fold off`. `/fold` alone moves to the next level. `/fold keys` shows what is bound, and `/fold calibrate` teaches the keys: it asks you to press your own Alt+1 … Alt+5 and remembers them, so the table above binds on any keyboard, not just the layout Alt+1…5 happens to arrive on. A folded reply tells you its level and how much of it you are seeing, and Alt+1 brings back every word. Short replies stay whole: one under about 80 words, or one a fold would barely shorten, always shows as written.

**Every reply at once.** A new level folds every reply in place, the earlier ones too, and the row above the prompt shows the five levels, the one you read at marked. Pi keeps each reply as it drew it, so the extension has the whole conversation drawn again when the level changes.

**The level survives a restart.** Each change is written to the session, and starting Pi again — or resuming a session — comes back at the level you read at; nothing is written twice for the same level. A restart tells you it restored, and the panel (below) names it even before any reply arrives.

**The panel shows the fold.** Under the row, a small panel previews the latest reply at the level in force — before any reply when a restart restored a level, and after one at the newest. It re-draws with every change, where the transcript's own copies only change when Pi re-renders them.

**Digits, on request.** `--textfold-digits` puts plain 1–5 to work: on an empty prompt a digit folds to its level; while you type it reinserts itself, so the digit you meant to write still lands (the flag is registered once a session starts, because Pi commits flags after extensions load — a bare digit otherwise gives up its key, which is why the short answer is Alt). Without the flag the Alt keys do everything.

**Why Alt.** Pi hands every key to its extensions before the prompt sees it, so a bare digit would never reach what you type.

**Any keyboard.** On most non-US layouts Alt+1…5 arrives as Alt plus a glyph (Alt+&, Alt+é, …), so the table above would bind nothing. `/fold calibrate` teaches the extension your own five keys — what you press is what it binds, on any layout Pi can name a key for. The teaching is kept in `~/.pi/agent/textfold-keys.json` and takes effect at once; `/fold keys` shows what is bound.

## Why you can trust a fold

Nothing is paraphrased. TextFold adds a short section to the system prompt that asks the model to lead with the point: the answer first in every reply, and the sentence that states its point first in every paragraph and list item. A fold keeps what the model put first. There is no second model and no summary, so a fold costs nothing, takes no time, and never puts words in the model's mouth. The fold is only on the screen: what the model sees of the conversation is never changed.

## Install

It needs Pi 1.2.0 or later, on Node 22.15 or later — every behavior above is verified on Pi 1.3.0; `--textfold-digits` is only as old as its flag support in Pi (the preflight script `scripts/check-pi-api.py` checks the APIs it needs against your installed pi).

```bash
git clone https://github.com/chenxiachan/textfold.git
pi install ./textfold/plugins/pi-textfold
```

Pi keeps the path, so leave the clone where it is. To try it for one session without installing it, start Pi with `pi -e ./textfold/plugins/pi-textfold`.

## Good to know

- The section changes the order of what the model writes, not what it says or how much. Pi runs many models: check on your own work that yours leads with the point, and does its work as well as before.
- `extension/fold.ts` is the Claude Code mod's own engine, and the section is the mod's own text. A test keeps both the same, so a reply folds the same way in Claude Code and in Pi.

The tests run with `npm install && npm test` in this folder. `tests/tui_smoke.py` drives the real Pi with a model and checks the keys; its first lines say how to run it.

TextFold for Pi was contributed by [Joseph Lam](https://github.com/jlamweil).
