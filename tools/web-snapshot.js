// A page as its reader sees it, serialized in the page itself (what a browser extension's content script would run):
// open shadow roots spelled out in place (their slots filled with what is assigned to them), an element the browser
// does not show (display none, visibility hidden, opacity 0) marked data-tf-css-hidden, each iframe a marker
// (<!--TF-FRAME-k-->) that the caller fills with that frame's own serialization. Scripts and styles are left out, but
// for JSON-LD, which says what the page is (and whether it is free to read).
(() => {
  const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const q = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  let frames = 0;
  const attrs = (el, extra) => {
    let s = '';
    for (const a of el.attributes) s += ` ${a.name}="${q(a.value)}"`;
    for (const [k, v] of extra) s += ` ${k}="${q(v)}"`;
    return s;
  };
  function ser(n, body) {
    if (n.nodeType === 3) return esc(n.data);
    if (n.nodeType !== 1) return '';
    const tag = n.localName;
    if (tag === 'slot') {
      const got = n.assignedNodes({ flatten: true });
      return (got.length ? got : [...n.childNodes]).map((c) => ser(c, body)).join('');
    }
    if (tag === 'script') return n.type === 'application/ld+json' ? `<script type="application/ld+json">${esc(n.textContent)}</script>` : '';
    if (tag === 'style' || tag === 'template' || tag === 'noscript') return '';
    const extra = [];
    if (body) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse' || parseFloat(cs.opacity) === 0) extra.push(['data-tf-css-hidden', '1']);
    }
    if (n.shadowRoot) extra.push(['data-tf-shadow', '1']);
    if (tag === 'iframe') {   // (marked on the page too, for the caller to find its frame)
      const k = String(frames++);
      n.setAttribute('data-tf-frame', k);
      return `<div${attrs(n, extra)}><!--TF-FRAME-${k}--></div>`;
    }
    if (VOID.has(tag)) return `<${tag}${attrs(n, extra)}>`;
    const kids = n.shadowRoot ? [...n.shadowRoot.childNodes] : [...n.childNodes];
    return `<${tag}${attrs(n, extra)}>${kids.map((c) => ser(c, body || tag === 'body')).join('')}</${tag}>`;
  }
  return `<!doctype html><html${attrs(document.documentElement, [])}>${ser(document.head, false)}${ser(document.body, true)}</html>`;
})()
