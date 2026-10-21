const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const root = path.join(__dirname, '..', 'textfold', 'web');

test('ordinary pages without WebMCP do not parse a second copy of the paper', () => {
  const context = vm.createContext({ document: {
    modelContext: undefined,
    getElementById: id => {
      if (id === 'documentation-chapter') return null;
      throw new Error('Unsupported ordinary page requested reader context');
    },
  } });
  assert.doesNotThrow(() => vm.runInContext(fs.readFileSync(path.join(root, 'webmcp.js'), 'utf8'), context));
});

function harness({ model = true, generateError = false, landing = true, zoteroResponse = { ref: '2605.00089', title: 'Fixture' } } = {}) {
  const calls = [], registered = [], papers = [];
  const fetch = async (url, options) => {
    calls.push({ url, options });
    const body = options?.headers?.['Content-Type'] === 'application/json' ? JSON.parse(options.body) : null;
    let data;
    if (url === '/api/import') { data = { paper: 'md-fixture', title: 'Fixture' }; papers.push({ id: data.paper, langs: ['en'] }); }
    else if (url === '/api/generate') {
      if (generateError) return { ok: false, json: async () => ({ error: 'model unavailable' }) };
      data = { id: 'generation', pid: body.paper, status: 'queued' };
    } else if (url === '/api/files') data = { job: { id: 'conversion', pid: 'doc-fixture', status: 'queued' }, via: 'file' };
    else if (url === '/api/papers') data = papers;
    else if (url === '/api/zotero/read') data = { ...zoteroResponse };
    else if (url === '/api/zotero' || url.startsWith('/api/zotero/items?')) data = [];
    else if (url === '/api/jobs') data = [{ id: 'generation', pid: 'md-fixture', readable: true, lang: 'en' }];
    else throw new Error(`Unexpected request: ${url}`);
    return { ok: true, json: async () => data };
  };
  const context = vm.createContext({ File, Uint8Array, atob, fetch, console, setTimeout: () => {},
    window: {}, readLang: 'sv', modelName: model ? 'fixture-model' : '', uiLang: 'zh',
    BOOT: { langs: { en: 'English', zh: '中文', sv: 'Svenska' } }, DATA: null,
    I18N: { CODES: ['en', 'zh'] }, refsOf: async () => ['10.1234/fixture'],
    document: { getElementById: id => id === 'lang' && landing ? { value: 'en' } : null,
      modelContext: { registerTool: t => { registered.push(t); } } } });
  // Run the shared upload section itself, without the unrelated sidebar/reader DOM.
  const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
  const upload = app.slice(app.indexOf('  async function uploadFile('), app.indexOf("  // OpenRouter's consent page"));
  vm.runInContext(`const api = async (url, body) => {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json(); if (!r.ok) throw new Error(d.error); return d;
  }; ${upload}`, context);
  vm.runInContext(fs.readFileSync(path.join(root, 'webmcp.js'), 'utf8'), context);
  const tool = registered.find(t => t.name === 'file-import');
  return { tool, calls, registered, uploads: context.window.TFUploads,
    runTool: async (name, args) => {
      const r = await registered.find(t => t.name === name).execute(args);
      assert.equal(!!r.isError, false, r.content[0].text);
      return JSON.parse(r.content[0].text);
    },
    run: async args => { const result = await tool.execute(args); return { error: !!result.isError, value: JSON.parse(result.content[0].text) }; } };
}

test('text upload preserves math, uses selected language and returns a readable source plus queued job', async () => {
  const h = harness(), text = '# Fixture\n\nInline $a^2$.\n\n$$x=1$$';
  const r = await h.run({ name: 'review.md', text });
  assert.equal(r.error, false);
  assert.equal(r.value.readable, true);
  assert.equal(r.value.nextRequiredAction, 'processing-status');
  assert.equal(JSON.parse(h.calls[0].options.body).text, text);
  assert.equal(JSON.parse(h.calls[1].options.body).lang, 'en');
});
test('base64 office bytes and explicit language use the existing binary endpoint', async () => {
  const h = harness(), bytes = Buffer.from('office fixture');
  const r = await h.run({ name: '文件.docx', base64: bytes.toString('base64'), lang: 'zh' });
  assert.equal(r.value.job.id, 'conversion');
  const upload = h.calls.find(c => c.url === '/api/files');
  assert.deepEqual(Buffer.from(await upload.options.body.arrayBuffer()), bytes);
  assert.equal(upload.options.headers['X-Lang'], 'zh');
  assert.equal(decodeURIComponent(upload.options.headers['X-Name']), '文件.docx');
});
test('PDF reference discovery stays in the shared upload operation', async () => {
  const h = harness();
  await h.run({ name: 'paper.pdf', base64: Buffer.from('%PDF-fixture').toString('base64') });
  const upload = h.calls.find(c => c.url === '/api/files');
  assert.deepEqual(JSON.parse(decodeURIComponent(upload.options.headers['X-Refs'])), ['10.1234/fixture']);
});
test('invalid payloads fail before any write', async () => {
  for (const args of [{name:'x.md'}, {name:'x.md', text:'x', base64:'eA=='}, {name:'x.pdf', text:'x'},
    {name:'x.md', text:' '}, {name:'x.md', base64:'!bad'}, {name:'x.md', text:'x', lang:'missing'},
    {name:'x.exe', base64:'eA=='}]) {
    const h = harness(), r = await h.run(args);
    assert.equal(r.error, true, JSON.stringify(args));
    assert.equal(h.calls.length, 0);
  }
});
test('missing model does not import text; generation failure preserves the saved source receipt', async () => {
  const noModel = harness({model:false});
  assert.equal((await noModel.run({name:'x.txt', text:'content'})).value.needs, 'model');
  assert.equal(noModel.calls.length, 0);
  const h = harness({generateError:true}), r = await h.run({name:'x.md', text:'content'});
  assert.equal(r.error, false);
  assert.equal(r.value.paper, 'md-fixture');
  assert.equal(r.value.readable, true);
  assert.equal(r.value.needs, 'generation');
});
test('base64 Markdown follows the text pipeline and schema declares exclusive payloads', async () => {
  const h = harness();
  const r = await h.run({name:'x.md', base64:Buffer.from('# 中文\n\n$x$').toString('base64')});
  assert.equal(r.value.job.id, 'generation');
  assert.equal(JSON.parse(h.calls[0].options.body).text, '# 中文\n\n$x$');
  assert.equal(h.tool.inputSchema.oneOf.length, 2);
  assert.equal(h.tool.annotations.readOnlyHint, false);
});
test('the shared upload enforces the existing file size limit before a request', async () => {
  const h = harness(), file = new File(['small fixture'], 'x.docx');
  Object.defineProperty(file, 'size', {value:100 * 1024 * 1024 + 1});
  await assert.rejects(h.uploads.importFile(file, 'en'), /too-large/);
  assert.equal(h.calls.length, 0);
});

test('reading languages beyond interface translations remain available', async () => {
  const h = harness();
  const r = await h.run({name: 'fixture.md', text: '# Fixture', lang: 'sv'});
  assert.equal(r.error, false);
  assert.equal(JSON.parse(h.calls.find(c => c.url === '/api/generate').options.body).lang, 'sv');
});

test('reader uploads default to the reading language when its interface falls back to English', async () => {
  const h = harness({landing: false});
  const r = await h.run({name: 'fixture.md', text: '# Fixture'});
  assert.equal(r.error, false);
  assert.equal(JSON.parse(h.calls.find(c => c.url === '/api/generate').options.body).lang, 'sv');
});

test('catalog exposes only existing functionality through 15 tools', () => {
  assert.deepEqual(harness().registered.map(t => t.name).sort(), [
    'library-query', 'library-open', 'file-import', 'zotero-query', 'zotero-import',
    'folder-create', 'folder-rename', 'document-move', 'reading-context', 'reading-navigate',
    'annotation-list', 'annotation-create', 'annotation-update', 'annotation-delete', 'processing-status',
  ].sort());
});

test('output from outside is marked untrusted, and a delete as consequential', () => {
  const hints = Object.fromEntries(harness().registered.map(t => [t.name, t.annotations]));
  const own = ['library-open', 'folder-create', 'folder-rename', 'document-move'];
  for (const [name, a] of Object.entries(hints)) assert.equal(!!a.untrustedContentHint, !own.includes(name), name);
  assert.equal(hints['annotation-delete'].consequentialHint, true);
  assert.equal(!!hints['annotation-create'].consequentialHint, false);
});

test('Zotero query delegates library listing and item search to existing endpoints', async () => {
  const h = harness();
  await h.runTool('zotero-query', {});
  await h.runTool('zotero-query', { library: 'users/0', query: 'fixture title' });
  assert.deepEqual(h.calls.map(c => c.url), ['/api/zotero', '/api/zotero/items?lib=users%2F0&q=fixture%20title']);
});

test('Zotero online import uses the existing item reader and normal language generation', async () => {
  const h = harness();
  const r = await h.runTool('zotero-import', { item: 'users/0/ABCD1234', lang: 'sv' });
  assert.deepEqual(JSON.parse(h.calls[0].options.body), { item: 'users/0/ABCD1234', lang: 'sv' });
  assert.deepEqual(JSON.parse(h.calls[1].options.body), { paper: '2605.00089', lang: 'sv', force: false });
  assert.equal(r.nextArgs.job, 'generation');
  assert.equal((await harness({ model: false }).runTool('zotero-import', { item: 'users/0/ABCD1234' })).needs, 'model');
});

test('Zotero file import retains existing conversion and engine-required receipts', async () => {
  const h = harness({ zoteroResponse: { job: { id: 'conversion', pid: 'doc-fixture' }, name: 'fixture.docx' } });
  const r = await h.runTool('zotero-import', { item: 'users/0/ABCD1234' });
  assert.equal(r.nextArgs.job, 'conversion');
  assert.equal(h.calls.some(c => c.url === '/api/generate'), false);
  const pending = await harness({ zoteroResponse: { needs: 'engine', upload: 'pdf-fixture' } }).runTool('zotero-import', { item: 'users/0/ABCD1234' });
  assert.equal(pending.upload, 'pdf-fixture');
  assert.match(pending.action, /conversion engine/);
});

test('processing status uses upstream job and language fields rather than a new paper-readable field', async () => {
  const h = harness();
  await h.run({ name: 'fixture.md', text: 'Fixture source' });
  const r = await h.runTool('processing-status', { job: 'generation', paper: 'md-fixture', open: true });
  assert.equal(r.readable, true);
  assert.equal(r.job.id, 'generation');
});
