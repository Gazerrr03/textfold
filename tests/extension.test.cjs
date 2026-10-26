const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// The browser's button (extension/background.js): the page and its frames sent as one, each frame's page put where its
// iframe is, by its address; a frame it could not read keeps its place empty. And what the manifest asks for.
const dir = path.join(__dirname, '..', 'extension');

function background() {
  const sent = [], badges = [];
  const chrome = {
    action: { onClicked: { addListener() {} }, setBadgeText: (b) => badges.push(b.text), setBadgeBackgroundColor() {}, setTitle() {} },
    scripting: { executeScript: async () => [
      { frameId: 0, result: { url: 'https://a.example/p', title: 'A', html: '<html><body><p>Top</p><div class="x" data-tf-frame="0" data-tf-frame-src="https://a.example/inner?a=1&amp;b=2"><!--TF-FRAME-0--></div><div data-tf-frame="1" data-tf-frame-src="https://ads.example/x"><!--TF-FRAME-1--></div></body></html>' } },
      { frameId: 7, result: { url: 'https://a.example/inner?a=1&b=2', title: '', html: '<html><head></head><body><p>Inside</p></body></html>' } },
    ] },
    runtime: { sendNativeMessage: async (host, msg) => { sent.push([host, msg]); return { ok: true, paper: 'web-a-example-1', open: null }; } },
    tabs: { create() {} },
  };
  const context = vm.createContext({ chrome, self: {}, console });
  vm.runInContext(fs.readFileSync(path.join(dir, 'background.js'), 'utf8'), context);
  return { capture: context.self.capture, sent, badges };
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

test('the extension asks for the tab it is clicked on, and nothing more', () => {
  const m = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
  assert.deepEqual(m.permissions.sort(), ['activeTab', 'nativeMessaging', 'scripting']);
  assert.equal(m.host_permissions, undefined);
  assert.equal(m.manifest_version, 3);
});
