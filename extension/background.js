// TextFold's button in the browser: the page in the tab, as its reader sees it (snapshot.js, in each frame the tab
// lets it into), sent to TextFold on this computer by native messaging (textfold/capture.py). The extension asks for
// the tab only when the reader clicks (activeTab): no page is read otherwise, and no port is opened on this computer.
const HOST = 'app.textfold.capture';

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

async function capture(tab) {
  badge(tab.id, '…', '#6b6f76');
  try {
    const got = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ['snapshot.js'] });
    const top = (got.find((r) => r.frameId === 0) || {}).result;
    if (!top || !top.html) throw new Error('no-page');
    const frames = got.filter((r) => r.frameId !== 0 && r.result && r.result.html).map((r) => r.result);
    const reply = await chrome.runtime.sendNativeMessage(HOST, {
      format: 'textfold/snapshot', version: 1, url: top.url, title: top.title, html: withFrames(top, frames),
      taken: new Date().toISOString(), how: 'extension',
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
self.capture = capture;   // (TextFold's tests call it as a click would)
