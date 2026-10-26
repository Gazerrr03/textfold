const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// The browser's button (extension/background.js): the page and its frames sent as one, each frame's page put where its
// iframe is, by its address; a frame it could not read keeps its place empty; the readings of reader.js sent with it,
// made in the top frame only, and the page sent without them when they fail. And what the manifest asks for.
const dir = path.join(__dirname, '..', 'extension');

const plain = (x) => JSON.parse(JSON.stringify(x));   // (from the extension's own context)
const READING = { defuddle: { html: '<p>Top</p>', title: 'A', words: 120 }, notes: 0, errors: [] };

function background(readerFails) {
  const sent = [], badges = [], scripts = [];
  const chrome = {
    action: { onClicked: { addListener() {} }, setBadgeText: (b) => badges.push(b.text), setBadgeBackgroundColor() {}, setTitle() {} },
    scripting: { executeScript: async (o) => {
      scripts.push(o);
      if (o.func) return [{ frameId: 0, result: READING }];
      if (o.files.includes('reader.js')) {
        if (readerFails) throw new Error('Cannot access contents of the page');
        return [{ frameId: 0, result: null }];
      }
      return [
        { frameId: 0, result: { url: 'https://a.example/p', title: 'A', html: '<html><body><p>Top</p><div class="x" data-tf-frame="0" data-tf-frame-src="https://a.example/inner?a=1&amp;b=2"><!--TF-FRAME-0--></div><div data-tf-frame="1" data-tf-frame-src="https://ads.example/x"><!--TF-FRAME-1--></div></body></html>' } },
        { frameId: 7, result: { url: 'https://a.example/inner?a=1&b=2', title: '', html: '<html><head></head><body><p>Inside</p></body></html>' } },
      ];
    } },
    runtime: { sendNativeMessage: async (host, msg) => { sent.push([host, msg]); return { ok: true, paper: 'web-a-example-1', open: null }; } },
    tabs: { create() {} },
  };
  const context = vm.createContext({ chrome, self: {}, console });
  vm.runInContext(fs.readFileSync(path.join(dir, 'background.js'), 'utf8'), context);
  return { capture: context.self.capture, mathSources: context.self.mathSources, sent, badges, scripts };
}

test('the frames are put in their places and the page is sent to TextFold', async () => {
  const b = background();
  const reply = await b.capture({ id: 3, index: 0 });
  assert.equal(reply.ok, true);
  const [host, msg] = b.sent[0];
  assert.equal(host, 'app.textfold.capture');
  assert.equal(msg.format, 'textfold/snapshot');
  assert.match(msg.html, /data-tf-frame-src="https:\/\/a\.example\/inner\?a=1&amp;b=2"><p>Inside<\/p><\/div>/);
  assert.match(msg.html, /<!--TF-FRAME-1-->/);   // (a frame the tab did not let it into: its place, empty)
  assert.deepEqual(b.badges, ['…', '✓']);
});

test('the readings are made in the top frame, on the snapshot sent, and sent with it', async () => {
  const b = background();
  await b.capture({ id: 3, index: 0 });
  const files = b.scripts.find((o) => o.files && o.files.includes('reader.js'));
  const call = b.scripts.find((o) => o.func && o.args);
  assert.deepEqual(plain(files.target), { tabId: 3, frameIds: [0] });
  assert.deepEqual(plain(files.files), ['vendor/defuddle/defuddle.js', 'vendor/readability/Readability.js', 'reader.js']);
  const [, msg] = b.sent[0];
  assert.equal(call.args[0], msg.html);
  assert.equal(call.args[1], 'https://a.example/p');
  assert.deepEqual(msg.read, READING);
});

test("MathJax's formulas are asked for their sources in the page's own world, before the snapshot", async () => {
  const b = background();
  await b.capture({ id: 3, index: 0 });
  assert.equal(b.scripts[0].world, 'MAIN');
  assert.equal(b.scripts[0].func.name, 'mathSources');
  assert.deepEqual(plain(b.scripts[1].files), ['snapshot.js']);
});

test("a page's MathJax 3 or 4, and 2: each formula's source written on its drawing", () => {
  const b = background();
  const els = [0, 1, 2].map(() => { const a = {}; return { setAttribute: (k, v) => { a[k] = v; }, a }; });
  const win = { MathJax: { startup: { document: { math: [
    { typesetRoot: els[0], math: 'y_i', display: false, inputJax: { name: 'TeX' } },
    { typesetRoot: els[1], math: '<math><mi>z</mi></math>', display: true, inputJax: { name: 'MathML' } },
  ] } } } };
  const run = (w, d) => vm.runInNewContext(`(${b.mathSources.toString()})()`, { window: w, document: d });
  assert.equal(run(win, {}), 2);
  assert.deepEqual(els[0].a, { 'data-tf-math': 'y_i', 'data-tf-math-in': 'tex' });
  assert.deepEqual(els[1].a, { 'data-tf-math': '<math><mi>z</mi></math>', 'data-tf-math-in': 'mathml', 'data-tf-math-display': 'block' });
  const v2 = { MathJax: { Hub: { getAllJax: () => [{ inputID: 'MathJax-Element-1', originalText: 'x^2', inputJax: 'TeX', root: { Get: () => 'inline' } }] } } };
  assert.equal(run(v2, { getElementById: (id) => (id === 'MathJax-Element-1-Frame' ? els[2] : null) }), 1);
  assert.equal(els[2].a['data-tf-math'], 'x^2');
  assert.equal(run({}, {}), 0);   // (no MathJax)
});

test('a page whose readings fail is sent all the same, with why', async () => {
  const b = background(true);
  const reply = await b.capture({ id: 3, index: 0 });
  assert.equal(reply.ok, true);
  const [, msg] = b.sent[0];
  assert.match(msg.read.errors[0], /Cannot access/);
  assert.match(msg.html, /<p>Inside<\/p>/);
});

test('the readers the extension runs are in it, each with its license', () => {
  for (const f of ['vendor/defuddle/defuddle.js', 'vendor/defuddle/LICENSE', 'vendor/readability/Readability.js',
                   'vendor/readability/LICENSE.md', 'reader.js']) {
    assert.ok(fs.existsSync(path.join(dir, f)), f);
  }
  assert.match(fs.readFileSync(path.join(dir, 'vendor/defuddle/defuddle.js'), 'utf8').slice(0, 2000), /changes:/);
});

test('the extension asks for the tab it is clicked on, and nothing more', () => {
  const m = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
  assert.deepEqual(m.permissions.sort(), ['activeTab', 'nativeMessaging', 'scripting']);
  assert.equal(m.host_permissions, undefined);
  assert.equal(m.manifest_version, 3);
});
