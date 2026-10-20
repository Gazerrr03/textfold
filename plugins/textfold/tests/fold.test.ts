import { describe, expect, test } from 'claude-code/testing'

import { blocks, firstSentence, fold, words, worthFolding } from '../hooks/fold'

const REPLY = `The bug was in the cache key, and it is fixed. Two requests for the same paper shared one key.

## What changed
The key now includes the language. That makes each translation its own entry. Old entries stay valid.

- Updated \`store.key()\` to take a language. It falls back to English.
- Added a test for two languages.

\`\`\`python
def key(pid, lang="en"):
    return f"{pid}:{lang}"
\`\`\`

## What to check
Run the tests once. They take about a minute, e.g. on a laptop.`

describe('sentences', () => {
  test('a first sentence ends at a stop and a space, never inside code or after an abbreviation', async () => {
    expect(firstSentence('It works. Then more.').head).toBe('It works.')
    expect(firstSentence('Use e.g. this one. Next.').head).toBe('Use e.g. this one.')
    expect(firstSentence('Call `a.b()` first. Then go.').head).toBe('Call `a.b()` first.')
    expect(firstSentence('Version 3.5 is out. Upgrade.').head).toBe('Version 3.5 is out.')
    expect(firstSentence('**It is fixed.** The rest.').head).toBe('**It is fixed.**')
    expect(firstSentence('One sentence only').more).toBe(false)
  })

  test('a Chinese stop ends a sentence without a space', async () => {
    expect(firstSentence('缓存键有问题，已经修好。同一篇论文的两次请求共用了一个键。').head).toBe('缓存键有问题，已经修好。')
  })
})

describe('folding', () => {
  test('the blocks of a reply', async () => {
    expect(blocks(REPLY).map((b) => b.kind)).toEqual(['para', 'heading', 'para', 'list', 'code', 'heading', 'para'])
  })

  test('Full is the reply as written', async () => {
    expect(fold(REPLY, 1).text).toBe(REPLY)
  })

  test('Brief keeps two sentences a paragraph and short code', async () => {
    const t = fold(REPLY, 2).text
    expect(t).toContain('The key now includes the language. That makes each translation its own entry. …')
    expect(t).not.toContain('Old entries stay valid.')
    expect(t).toContain('def key(pid, lang="en"):')
  })

  test('Points keeps one sentence a paragraph and item, and folds code to a line', async () => {
    const t = fold(REPLY, 3).text
    expect(t).toContain('The bug was in the cache key, and it is fixed. …')
    expect(t).toContain('- Updated `store.key()` to take a language. …')
    expect(t).toContain('`⋯ 2 lines of code`')
    expect(t).not.toContain('def key')
  })

  test('Outline keeps the headings and the first sentence under each', async () => {
    const t = fold(REPLY, 4).text
    expect(t).toBe(
      'The bug was in the cache key, and it is fixed. …\n\n## What changed\n\nThe key now includes the language. …\n\n## What to check\n\nRun the tests once. …',
    )
  })

  test('Gist is the reply’s first sentence', async () => {
    expect(fold(REPLY, 5).text).toBe('The bug was in the cache key, and it is fixed. …')
  })

  test('a table straight after a paragraph is its own block', async () => {
    const md = 'The options compare like this.\n| Option | Cost |\n| --- | --- |\n| A | free |\n| B | 5/mo |'
    expect(blocks(md).map((b) => b.kind)).toEqual(['para', 'table'])
  })

  test('a table without leading pipes is a table, not a paragraph joined into one line', async () => {
    const md = 'Option | Cost\n:-- | --:\nA | free\nB | 5/mo'
    expect(blocks(md)).toEqual([{ kind: 'table', lines: md.split('\n') }])
    expect(blocks('A heading\n---').map((b) => b.kind)).toEqual(['para'])
  })

  test('each level shows fewer words', async () => {
    const counts = [1, 2, 3, 4, 5].map((n) => fold(REPLY, n).shown)
    for (let i = 1; i < counts.length; i++) expect(counts[i]!).toBeLessThan(counts[i - 1]!)
    expect(words('缓存键 cache key')).toBe(5)
  })
})

describe('the gate', () => {
  const long = Array.from({ length: 12 }, (_, i) => `Sentence ${i} has a few words in it.`).join(' ')

  test('a reply under 80 words is never folded', async () => {
    expect(worthFolding(REPLY, fold(REPLY, 5).text)).toBe(false)
  })

  test('a long reply is folded when the fold hides a quarter of it or more', async () => {
    expect(worthFolding(long, fold(long, 3).text)).toBe(true)
    expect(worthFolding(long, long.slice(0, Math.round(long.length * 0.8)))).toBe(false)
  })

  test('Chinese counts by reading effort, not by character', async () => {
    expect(worthFolding('缓'.repeat(140), '缓')).toBe(true)
    expect(worthFolding('缓'.repeat(120), '缓')).toBe(false)
  })
})

describe('drawings', () => {
  // Pi's mermaid renderer turns a mermaid block into these rows before any extension sees the reply.
  const art = ['`┌────┐    ┌──────────┐    ┌────────┐`  ', '`│ Pi ├───▶│ TextFold ├───▶│ Screen │`  ', '`└────┘    └──────────┘    └────────┘`'].join('\n')
  const md = `The reply goes through three steps. Each one changes it.\n\n${art}\n\nThe fold is the second step. It runs after the drawing.`

  test('a drawing is one block, kept row by row at Brief and Points, and gone at Outline and Gist', async () => {
    expect(blocks(md).map((b) => b.kind)).toEqual(['para', 'art', 'para'])
    expect(fold(md, 2).text).toContain(art)
    expect(fold(md, 3).text).toContain(art)
    expect(fold(md, 4).text).not.toContain('TextFold ├')
    expect(fold(md, 5).text).not.toContain('TextFold ├')
  })

  test('a paragraph of one code span is still a paragraph', async () => {
    expect(blocks('`npm test`').map((b) => b.kind)).toEqual(['para'])
  })
})
