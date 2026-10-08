// 一个刚够用的 DOM 替身：让 pro.js 的渲染与 polishPanels 能在 Node 里真跑一遍。
// 只实现这些函数真正用到的东西（不追求完整 DOM）。
function El(tag) {
  this.tagName = String(tag || "div").toUpperCase();
  this.children = []; this.attributes = {}; this.dataset = {}; this.style = {};
  this._text = ""; this._html = ""; this.className = ""; this.parentNode = null;
  this.classList = {
    _o: this,
    add: (c) => { this.className = (this.className ? this.className + " " : "") + c; },
    remove: (c) => { this.className = this.className.split(/\s+/).filter((x) => x && x !== c).join(" "); },
    contains: (c) => this.className.split(/\s+/).indexOf(c) >= 0,
    toggle: (c, on) => { if (on) this.classList.add(c); else this.classList.remove(c); },
  };
}
Object.defineProperty(El.prototype, "textContent", {
  get() { return this._text; },
  set(v) { this._text = String(v == null ? "" : v); this.children = []; },
});
Object.defineProperty(El.prototype, "innerHTML", {
  get() { return this._html; },
  set(v) { this._html = String(v == null ? "" : v); this.children = []; this._parsed = true; },
});
El.prototype.appendChild = function (c) { c.parentNode = this; this.children.push(c); this._html += ""; return c; };
El.prototype.insertBefore = function (c, ref) {
  const i = ref ? this.children.indexOf(ref) : -1;
  if (i >= 0) this.children.splice(i, 0, c); else this.children.push(c);
  c.parentNode = this; return c;
};
El.prototype.setAttribute = function (k, v) { this.attributes[k] = String(v); };
El.prototype.getAttribute = function (k) { return this.attributes[k]; };
// 选择器只支持：#id / .class / tag / [attr] / [attr="v"] 与它们的组合（够用即可）
function matches(el, sel) {
  return sel.split(/(?=[.#\[])/).every((part) => {
    if (!part) return true;
    if (part[0] === "#") return el.attributes.id === part.slice(1);
    if (part[0] === ".") return el.classList.contains(part.slice(1));
    if (part[0] === "[") {
      const m = part.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
      if (!m) return false;
      return m[2] === undefined ? el.attributes[m[1]] !== undefined : el.attributes[m[1]] === m[2];
    }
    return el.tagName === part.toUpperCase();
  });
}
El.prototype._all = function (out) { (this.children || []).forEach((c) => { out.push(c); c._all(out); }); return out; };
El.prototype.querySelector = function (sel) { return this._all([]).find((e) => matches(e, sel)) || null; };
El.prototype.querySelectorAll = function (sel) { return this._all([]).filter((e) => matches(e, sel)); };

function makeDocument() {
  const doc = {
    _els: {},
    createElement: (t) => new El(t),
    querySelector: (sel) => doc.body.querySelector(sel),
    querySelectorAll: (sel) => doc.body.querySelectorAll(sel),
    addEventListener: () => {},
  };
  doc.body = new El("body");
  doc.documentElement = new El("html");
  return doc;
}
module.exports = { El, makeDocument, matches };
