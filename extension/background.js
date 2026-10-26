// TextFold's button in the browser: the page in the tab, as its reader sees it (snapshot.js, in each frame the tab
// lets it into), and its article as reading views read it (reader.js, on that snapshot), sent to TextFold on this
// computer by native messaging (textfold/capture.py). The extension asks for the tab only when the reader clicks
// (activeTab): no page is read otherwise, and no port is opened on this computer.
const HOST = 'app.textfold.capture';
const READERS = ['vendor/defuddle/defuddle.js', 'vendor/readability/Readability.js', 'reader.js'];

const badge = (tabId, text, color) => {
  chrome.action.setBadgeText({ tabId, text });
  if (color) chrome.action.setBadgeBackgroundColor({ tabId, color });
};

// the frames' own pages, put where the page shows them (by their address, in order)
function withFrames(top, frames) {
  const left = [...frames];
  const unq = (s) => s.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
  return top.html.replace(/<div([^>]*?) data-tf-frame-src="([^"]*)"([^>]*)><!--TF-FRAME-(\d+)--><\/div>/g, (all, a, src, b) => {
    const i = left.findIndex((f) => f.url === unq(src));
    if (i < 0) return all;
    const body = /<body[^>]*>([\s\S]*)<\/body>/.exec(left.splice(i, 1)[0].html);
    return `<div${a} data-tf-frame-src="${src}"${b}>${body ? body[1] : ''}</div>`;
  });
}

// Run in the page's own world, not the extension's: where the page's MathJax drew a formula (its drawing has no
// MathML in it since MathJax 4), the formula's source, TeX or MathML, written on the drawing (data-tf-math) for the
// snapshot to keep. MathJax 3 and 4 list their formulas in startup.document.math, MathJax 2 in Hub.getAllJax().
// Nothing else of the page is read or changed.
function mathSources() {
  const MJ = window.MathJax;
  let n = 0;
  const mark = (el, src, mathml, display) => {
    if (!el || !el.setAttribute || typeof src !== 'string' || !src.trim()) return;
    el.setAttribute('data-tf-math', src.trim());
    el.setAttribute('data-tf-math-in', mathml ? 'mathml' : 'tex');
    if (display) el.setAttribute('data-tf-math-display', 'block');
    n += 1;
  };
  try {
    const doc = MJ && MJ.startup && MJ.startup.document;
    if (doc && doc.math) {
      for (const item of doc.math) mark(item.typesetRoot, item.math, /mathml/i.test((item.inputJax && item.inputJax.name) || ''), item.display);
    } else if (MJ && MJ.Hub && MJ.Hub.getAllJax) {
      for (const jax of MJ.Hub.getAllJax()) {
        const frame = document.getElementById(`${jax.inputID}-Frame`);
        const display = !!(jax.root && jax.root.Get && jax.root.Get('display') === 'block');
        mark(display && frame ? frame.parentNode : frame, jax.originalText, /mathml/i.test(String(jax.inputJax || '')), display);
      }
    }
  } catch (e) { /* a MathJax of another make: its formulas are read as drawn */ }
  return n;
}

// the snapshot's article, read in the tab's page (a service worker has no DOM to read it in); what went wrong, if
// either reader failed: TextFold reads the snapshot itself then
async function readings(tabId, html, url) {
  try {
    const target = { tabId, frameIds: [0] };
    await chrome.scripting.executeScript({ target, files: READERS });
    const [r] = await chrome.scripting.executeScript({ target, func: (h, u) => self.tfRead(h, u), args: [html, url] });
    return (r && r.result) || { errors: ['no-result'] };
  } catch (e) {
    return { errors: [String(e && e.message)] };
  }
}

async function capture(tab) {
  badge(tab.id, '…', '#6b6f76');
  try {
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, world: 'MAIN', func: mathSources });
    } catch (e) { /* a frame it may not run in: its formulas are read as drawn */ }
    const got = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ['snapshot.js'] });
    const top = (got.find((r) => r.frameId === 0) || {}).result;
    if (!top || !top.html) throw new Error('no-page');
    const frames = got.filter((r) => r.frameId !== 0 && r.result && r.result.html).map((r) => r.result);
    const html = withFrames(top, frames);
    const reply = await chrome.runtime.sendNativeMessage(HOST, {
      format: 'textfold/snapshot', version: 1, url: top.url, title: top.title, html,
      read: await readings(tab.id, html, top.url), taken: new Date().toISOString(), how: 'extension',
    });
    if (!reply || !reply.ok) throw new Error((reply && reply.error) || 'no-reply');
    badge(tab.id, '✓', '#3f7d52');
    if (reply.open) chrome.tabs.create({ url: reply.open, index: tab.index + 1 });
    return reply;
  } catch (e) {
    badge(tab.id, '!', '#b3412e');
    chrome.action.setTitle({ tabId: tab.id, title: `TextFold: ${e.message}` });
    return { ok: false, error: e.message };
  }
}

chrome.action.onClicked.addListener(capture);
self.capture = capture;   // (TextFold's tests call it as a click would, and mathSources on pages of their own)
self.mathSources = mathSources;
