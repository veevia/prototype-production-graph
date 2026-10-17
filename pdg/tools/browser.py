"""N13 pre-check: the real-browser prototype suite (Playwright Chromium + vendored axe-core).

`run_suite` is a pure function over an entry file, scenarios, states and screens, so it is reusable outside the graph
(`python -m pdg check-prototype …`). Per viewport it runs every scenario in a fresh context (isolated storage), then
sweeps every screen (its route must render its `[data-screen]` in that fresh session) and planned state: axe (WCAG 2.0/2.1/2.2 A+AA tags), horizontal overflow, reflow at 320 px, pointer
target sizes (24 px AA, 44 px on mobile), rendered text size, keyboard focus visibility, focus not wholly
obscured, text spacing clipping, reduced motion, console errors, page errors, any request outside file:/data:,
and DOMContentLoaded timing. Every finding carries a trace
(the node that implements it), the smallest fix and an acceptance check, so the gate can route it without guessing.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from ..context import CheckResult, NodeContext
from ..util import PKG_ROOT, write_json_atomic
from ._common import finding, luminance

IMPL = "n11_prototype_development"
ALLOWED_SCHEMES = ("file:", "data:", "blob:", "about:")

JS_LABEL = """(e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
    (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')"""
# the page scrolls in the document or in a region around the view (an app shell's main area with overflow auto under a
# fixed header): what that region scrolls sideways moves the whole screen, so it is page overflow, never content
# "reachable in its scroller". The document stayed as wide as the window while a legend ran 490 px past its card inside
# the app's main area, and RESP-OVERFLOW, RESP-BAND and RESP-TEXT all passed (field run 2, R2-27)
JS_VIEW_SCROLLERS = """() => { const out = [];
    for (const v of document.querySelectorAll('[data-screen]')) {
      if (!v.checkVisibility()) continue;
      for (let a = v; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
        const cs = getComputedStyle(a);   // a pane that snaps sideways (swiped panels) scrolls so on purpose (review S6)
        if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && !/\\b(x|both|inline)\\b/.test(cs.scrollSnapType)
            && !out.includes(a)) out.push(a); } }
    return out; }"""
# {px, by}: how far the page runs past the window, and the region around the view that scrolls it, if not the document
JS_PAGE_OVERFLOW = """
  const label = """ + JS_LABEL + """;
  let overflow = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) - window.innerWidth;
  let overflowIn = '';
  const viewScrollers = (""" + JS_VIEW_SCROLLERS + """)();
  for (const s of viewScrollers) { const d = s.scrollWidth - s.clientWidth; if (d > overflow) { overflow = d; overflowIn = label(s); } }
"""
JS_OVERFLOW = "() => {" + JS_PAGE_OVERFLOW + "  return {px: overflow, by: overflowIn};\n}"
JS_TARGETS = """(minPx) => {
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=tab],[role=link],[role=checkbox],[role=switch],[tabindex]:not([tabindex="-1"])';
  const out = [];
  for (const e of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    let r = e.getBoundingClientRect(); if (r.width === 0 && r.height === 0) continue;
    if ((e.type === 'checkbox' || e.type === 'radio') && e.closest('label')) r = e.closest('label').getBoundingClientRect();
    const inlineLink = e.tagName === 'A' && cs.display === 'inline' && e.parentElement && /\\S/.test((e.parentElement.textContent || '').replace(e.textContent, ''));
    if (inlineLink) continue;
    if (r.width + 0.5 < minPx || r.height + 0.5 < minPx) out.push({tag: e.tagName.toLowerCase(), id: e.id || '', cls: (e.className && e.className.baseVal === undefined ? e.className : '').toString().slice(0, 60), text: (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height)});
  }
  return out;
}"""
JS_TEXT = """(minPx) => {
  const out = []; const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode; if (!/\\S/.test(n.textContent)) continue;
    const el = n.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    if (el.closest('[aria-hidden="true"],script,style,noscript,template')) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = el.getBoundingClientRect(); if (r.width <= 1 || r.height <= 1) continue;
    const size = parseFloat(cs.fontSize); if (size + 0.01 < minPx) out.push({tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 60), size, text: n.textContent.trim().slice(0, 40)});
  }
  return out;
}"""
JS_FOCUS = """() => {
  const e = document.activeElement; if (!e || e === document.body) return null;
  const cs = getComputedStyle(e);
  const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
  const shadow = cs.boxShadow && cs.boxShadow !== 'none';
  window.__pdgFocusId = window.__pdgFocusId || 0;
  if (!e.dataset.pdgFocusId) e.dataset.pdgFocusId = String(++window.__pdgFocusId);
  return {uid: e.dataset.pdgFocusId, tag: e.tagName.toLowerCase(), id: e.id || '', text: (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 40), visible: outline || shadow};
}"""
# the focused control's box and a margin round it, in the viewport (where a screenshot's clip is), or null off-screen
JS_FOCUS_BOX = """(pad) => { const e = document.activeElement; if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect();
  const x = Math.max(0, r.left - pad), y = Math.max(0, r.top - pad);
  const w = Math.min(innerWidth, r.right + pad) - x, h = Math.min(innerHeight, r.bottom + pad) - y;
  window.__pdgWalk = e;
  return w >= 1 && h >= 1 ? {x, y, width: w, height: h} : null; }"""
# armed before each Tab: the attributes the move changes (a class a script adds on focus and keeps after blur, as a chart
# point marks itself), so the page before the move can be put back and read
JS_ARM_MUT = """() => { if (window.__pdgObs) window.__pdgObs.disconnect(); window.__pdgMut = [];
  window.__pdgPrevFocus = document.activeElement;
  window.__pdgObs = new MutationObserver((rs) => { for (const r of rs) if (!r.attributeName.startsWith('data-pdg'))
    window.__pdgMut.push([r.target, r.attributeName, r.oldValue]); });
  window.__pdgObs.observe(document.documentElement, {attributes: true, attributeOldValue: true, subtree: true}); }"""
# the page as before the move: the control blurred, then each attribute the move changed on it, inside it or round it
# set back to its value before it. Not on the stop the move left: its own blur change, put back, could draw inside this
# box and read as this stop's indicator
JS_BEFORE_FOCUS = """() => { const o = window.__pdgObs, muts = window.__pdgMut || [], w = window.__pdgWalk;
  if (o) { for (const r of o.takeRecords()) if (!r.attributeName.startsWith('data-pdg')) muts.push([r.target, r.attributeName, r.oldValue]);
    o.disconnect(); window.__pdgObs = null; }
  const back = new Map();   // element -> attribute -> [its value now, its value before the move]
  for (const [el, name, old] of muts) { if (!(el === w || w.contains(el) || el.contains(w))) continue;
    if (!back.has(el)) back.set(el, new Map());
    if (!back.get(el).has(name)) back.get(el).set(name, [el.getAttribute(name), old]); }
  window.__pdgBack = back; w.blur();
  for (const [el, m] of back) for (const [name, [, old]] of m) old === null ? el.removeAttribute(name) : el.setAttribute(name, old); }"""
JS_AFTER_FOCUS = """() => { const back = window.__pdgBack; window.__pdgBack = null;
  if (back) for (const [el, m] of back) for (const [name, [now]] of m) now === null ? el.removeAttribute(name) : el.setAttribute(name, now);
  const e = window.__pdgWalk; if (e && e.isConnected && document.activeElement !== e) e.focus({preventScroll: true, focusVisible: true}); }"""
JS_PREV_FOCUS = """() => {
  if (window.__pdgObs) { for (const r of window.__pdgObs.takeRecords()) if (!r.attributeName.startsWith('data-pdg'))
    window.__pdgMut.push([r.target, r.attributeName, r.oldValue]); window.__pdgObs.disconnect(); window.__pdgObs = null; }
  const p = window.__pdgPrevFocus;
  if (p && p !== document.body && p.isConnected && p.focus) p.focus({preventScroll: true, focusVisible: true});
  else if (window.__pdgWalk && window.__pdgWalk.blur) window.__pdgWalk.blur();
}"""
JS_INSTANT_SCROLL = """
  if (!document.getElementById('pdg-instant-scroll')) {
    const s = document.createElement('style'); s.id = 'pdg-instant-scroll';
    s.textContent = '*{scroll-behavior:auto!important}'; document.head.appendChild(s);
  }"""
JS_RESET_FOCUS = """() => {""" + JS_INSTANT_SCROLL + """
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  const b = document.body, had = b.hasAttribute('tabindex');
  if (!had) b.setAttribute('tabindex', '-1');
  b.focus({preventScroll: true});
  if (!had) b.removeAttribute('tabindex');
  window.scrollTo(0, 0);
}"""   # instant scroll, or a smooth-scrolling page reads mid-scroll as obscured; the walk starts at the page's top (audit #1, #11)
JS_FOCUS_OBSCURED = """() => {
  const e = document.activeElement; if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(); if (r.width <= 0 || r.height <= 0) return null;
  window.__pdgFocusId = window.__pdgFocusId || 0;
  if (!e.dataset.pdgFocusId) e.dataset.pdgFocusId = String(++window.__pdgFocusId);
  let fixed = false;
  for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
    const pos = getComputedStyle(n).position;
    if (pos === 'fixed' || pos === 'sticky') { fixed = true; break; }
  }
  const text = (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 60);
  const cls = (e.className && e.className.baseVal === undefined ? e.className : '').toString().slice(0, 60);
  if (fixed) return {uid: e.dataset.pdgFocusId, tag: e.tagName.toLowerCase(), id: e.id || '', cls, text, hidden: false, fixed: true};
  // the points are read in the part of the stop that is shown: the viewport and every box that clips it (overflow)
  // cut its rect first. Read across its whole rect, a scroll region taller than the viewport and a stop an app's
  // scroller shows a strip of fell off-screen or on the chrome above it: only a stop wholly hidden fails 2.4.11
  // (refresh field run)
  let vl = Math.max(0, r.left), vt = Math.max(0, r.top), vr = Math.min(window.innerWidth, r.right),
      vb = Math.min(window.innerHeight, r.bottom), clip = '';
  const onScreen = vr - vl >= 1 && vb - vt >= 1;
  for (let a = e.parentElement; onScreen && a && a !== document.documentElement; a = a.parentElement) {
    const acs = getComputedStyle(a);
    if (acs.overflowX === 'visible' && acs.overflowY === 'visible') continue;
    const b = a.getBoundingClientRect();
    if (acs.overflowX !== 'visible') { vl = Math.max(vl, b.left); vr = Math.min(vr, b.right); }
    if (acs.overflowY !== 'visible') { vt = Math.max(vt, b.top); vb = Math.min(vb, b.bottom); }
    if (!clip && (vr - vl < 1 || vb - vt < 1)) clip = a.tagName.toLowerCase() + (a.id ? '#' + a.id : '');
  }
  const shown = vr - vl >= 1 && vb - vt >= 1;
  const at = (x0, y0, x1, y1) => [[0.5, 0.5], [0.1, 0.2], [0.9, 0.8]].map(([x, y]) =>
    document.elementFromPoint(x0 + (x1 - x0) * x, y0 + (y1 - y0) * y));
  // and in the part inside the viewport: hit testing honours every clip, so a stop that escapes a box the walk above
  // counted (an absolutely placed one) is found there, and a clipped one is not
  const pts = (shown ? at(vl, vt, vr, vb) : []).concat(onScreen ? at(Math.max(0, r.left), Math.max(0, r.top),
    Math.min(window.innerWidth, r.right), Math.min(window.innerHeight, r.bottom)) : []);
  const hits = pts.some(hit => hit && (hit === e || e.contains(hit)));
  if (hits || shown) clip = '';
  const over = hits || clip ? null : pts.find(hit => hit);
  const cover = over ? over.tagName.toLowerCase() + (over.id ? '#' + over.id : '')
    + ((over.className && over.className.baseVal === undefined && over.className) ? '.' + over.className.toString().trim().split(/\\s+/).slice(0, 2).join('.') : '') : '';
  const offscreen = !onScreen;   // nothing covers it: it is outside the viewport (R2-22)
  return {uid: e.dataset.pdgFocusId, tag: e.tagName.toLowerCase(), id: e.id || '', cls, text, hidden: !hits,
          fixed: false, top: Math.round(r.top), bottom: Math.round(r.bottom), cover, offscreen, clip};
}"""
TEXT_SPACING_STYLE = "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }"
JS_TEXT_SPACING = """(cap) => {
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el.closest('[aria-hidden="true"],script,style,noscript,template')) continue;
    const txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (!txt) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    const clipX = (cs.overflowX === 'hidden' || cs.overflowX === 'clip') && el.scrollWidth > el.clientWidth + 1;
    const clipY = (cs.overflowY === 'hidden' || cs.overflowY === 'clip') && el.scrollHeight > el.clientHeight + 1;
    if (clipX || clipY) out.push({tag: el.tagName.toLowerCase(), id: el.id || '',
      cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 60),
      text: txt.slice(0, 70), scrollW: el.scrollWidth, clientW: el.clientWidth, scrollH: el.scrollHeight,
      clientH: el.clientHeight, axis: clipX && clipY ? 'both' : (clipX ? 'horizontal' : 'vertical')});
    if (out.length >= cap) break;
  }
  return out;
}"""
JS_MOTION = """(maxS) => {
  const out = [];
  for (const e of document.querySelectorAll('*')) {
    const cs = getComputedStyle(e);
    const d = [cs.animationDuration, cs.transitionDuration].join(',').split(',').map(x => parseFloat(x) * (x.trim().endsWith('ms') ? 0.001 : 1));
    if (d.some(v => v > maxS)) out.push({tag: e.tagName.toLowerCase(), cls: (e.className || '').toString().slice(0, 50), dur: Math.max(...d)});
    if (out.length > 20) break;
  }
  return out;
}"""
JS_TIMING = "() => { const n = performance.getEntriesByType('navigation')[0]; return n ? n.domContentLoadedEventEnd : null; }"
# a goto to the URL the page is on: back to the top of the window and of every scroller, and focus released so Tab
# starts from the top (a bare blur leaves Chromium's Tab starting point where focus was). On a page with
# scroll-behavior: smooth, a scroll the last step started keeps running through an instant reset, so the reset waits
# until nothing has moved for 3 frames (at most 120), then jumps (W50 review I3)
JS_ARRIVE = """async () => {
  const where = () => window.scrollX + ',' + window.scrollY + ';'
    + Array.from(document.querySelectorAll('*'), (e) => e.scrollTop + ',' + e.scrollLeft).join(';');
  const frame = () => new Promise((r) => { requestAnimationFrame(() => r()); setTimeout(r, 50); });   // frames may stop
  let last = where(), still = 0;
  for (let i = 0; i < 120 && still < 3; i++) { await frame(); const now = where(); still = now === last ? still + 1 : 0; last = now; }
  for (const el of document.querySelectorAll('*'))   // <html> among them: its scroll is the window's
    if (el.scrollTop || el.scrollLeft) el.scrollTo({top: 0, left: 0, behavior: 'instant'});
  const b = document.body, had = b.hasAttribute('tabindex');
  if (!had) b.setAttribute('tabindex', '-1');
  b.focus({preventScroll: true});
  b.blur();
  if (!had) b.removeAttribute('tabindex');
}"""
JS_REACHABLE = "(e) => { const r = e.getBoundingClientRect(); return r.bottom > -window.innerHeight && r.top < 2 * window.innerHeight; }"
# in view without scrolling: inside the window and inside every scrolling or clipping container around it (a dialog's
# body, a pane); Playwright's "visible" means only "has a box" (field run 2, R2-23: a Create button 219 px below its
# dialog's visible box passed)
JS_IN_VIEW = """(e) => {
  const r = e.getBoundingClientRect();
  if (!(r.top >= 0 && r.top < window.innerHeight && r.bottom > 0))
    return 'outside the window (its top at ' + Math.round(r.top) + ' px, the window ' + window.innerHeight + ' px high)';
  for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
    const cs = getComputedStyle(a);
    if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
    const b = a.getBoundingClientRect();
    if (!(r.top >= b.top - 1 && r.top < b.bottom && r.bottom > b.top))
      return 'outside ' + a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + (typeof a.className === 'string' && a.className.trim()
        ? '.' + a.className.trim().split(/\\s+/)[0] : '') + ', which shows ' + Math.round(b.top) + '–' + Math.round(b.bottom)
        + ' px (its top at ' + Math.round(r.top) + ' px)';
  }
  return '';
}"""
# B-09: after a state renders, focus its first control and watch the page: a panel rebuilt four times a second, or a
# live region re-inserted, passed FUNC-STATES because only the marker was checked. The marker element comes from
# Playwright's selector engine, as in the render check; every element added or removed anywhere on the page counts,
# its descendants included (config batch 2 review I2, I3).
JS_STATE_WATCH = """(m) => {
  const sel = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),' +
              '[tabindex]:not([tabindex="-1"])';
  const target = m ? (m.matches(sel) ? m : m.querySelector(sel)) : null;
  if (target) target.focus();
  const live = (n) => n.nodeType === 1 && (n.matches('[role=alert],[role=status],[aria-live]') ||
                                           !!n.querySelector('[role=alert],[role=status],[aria-live]'));
  const size = (n) => n.nodeType === 1 ? 1 + n.getElementsByTagName('*').length : 0;
  const w = window.__pdgWatch = {changes: 0, live: 0, target, href: location.href,
                                 focused: !!target && document.activeElement === target,
                                 busy: !!(m && m.closest('[aria-busy="true"]'))};
  w.obs = new MutationObserver((list) => { for (const r of list) {
    for (const n of r.addedNodes) { w.changes += size(n); if (live(n)) w.live += 1; }
    for (const n of r.removedNodes) w.changes += size(n); } });
  w.obs.observe(document.body, {childList: true, subtree: true});
  const root = m ? m.getRootNode() : document;
  if (root !== document) w.obs.observe(root, {childList: true, subtree: true});
  return {control: target ? (target.id ? '#' + target.id : target.tagName.toLowerCase() +
          (target.textContent ? ' "' + target.textContent.trim().slice(0, 30) + '"' : '')) : null,
          focused: w.focused, busy: w.busy};
}"""
JS_STATE_WATCH_END = """() => { const w = window.__pdgWatch; if (!w) return {left: true}; w.obs.disconnect();
  return {changes: w.changes, live: w.live, left: location.href !== w.href,
          held: w.focused ? (w.target.isConnected && document.activeElement === w.target) : null}; }"""
# B-08: a custom property used without a fallback where it is undefined makes the declaration invalid, so the element
# loses its fill or its edge; `--x: var(--x)` is undefined. A property declared empty on purpose (Tailwind's
# `--tw-ring-inset: ;` or `var(--tw-empty,/*!*/ /*!*/)`) is not undefined; a rule in a media query that does not apply,
# or on a pseudo-element, is judged where it applies (config batch 2 review C1). Also: each design-system colour the
# page defines, resolved by the browser.
JS_TOKENS = """([dsTokens, maxRules, extraCss]) => {
  const bare = (text) => { const out = []; let i = 0;
    while ((i = text.indexOf('var(', i)) !== -1) {
      let depth = 0, j = i + 3, comma = false;
      for (; j < text.length; j++) { const c = text[j];
        if (c === '(') depth++; else if (c === ')') { if (--depth === 0) break; } else if (c === ',' && depth === 1) comma = true; }
      if (comma) { i = j + 1; continue; }
      const m = /^\\s*(--[\\w-]+)\\s*$/.exec(text.slice(i + 4, j)); if (m) out.push(m[1]); i += 4; }
    return out; };
  const PSEUDO = /::?(before|after|placeholder|marker|selection|first-line|first-letter|backdrop)\\b/g;
  const empties = new Set(), pending = [], undef = {}, unreadable = [];
  let rules = 0, containers = 0, rejected = 0;
  const applies = (r) => {
    if (typeof CSSMediaRule !== 'undefined' && r instanceof CSSMediaRule) return window.matchMedia(r.media.mediaText).matches;
    if (typeof CSSSupportsRule !== 'undefined' && r instanceof CSSSupportsRule) return CSS.supports(r.conditionText);
    if (typeof CSSContainerRule !== 'undefined' && r instanceof CSSContainerRule) return null;
    return true; };
  const declare = (style) => { for (let k = 0; k < style.length; k++) { const p = style[k]; if (!p.startsWith('--')) continue;
    const v = style.getPropertyValue(p).replace(/\\/\\*[\\s\\S]*?\\*\\//g, '').trim();
    if (v === '' || /^var\\(\\s*--[\\w-]+\\s*,\\s*\\)$/.test(v)) empties.add(p); } };
  const visit = (list, scope, parent) => { for (const r of list) {
    if (rules >= maxRules) return;
    if (r instanceof CSSStyleRule) {
      let sel = r.selectorText;
      if (parent) sel = sel.includes('&') ? sel.split('&').join(':is(' + parent + ')') : ':is(' + parent + ') ' + sel;
      declare(r.style);
      const names = [...new Set(bare(r.style.cssText))];
      if (names.length) { rules += 1;
        const pm = /::?(before|after|placeholder|marker|selection|first-line|first-letter|backdrop)\\b/.exec(sel);
        let host = sel.replace(PSEUDO, '').trim() || '*';   // `*, ::before, ::after` leaves empty list items
        if (!host.includes('(')) host = host.split(',').map((x) => x.trim() || '*').join(', ');
        let els = []; try { els = Array.from(scope.querySelectorAll(host)).slice(0, 5); } catch (e) { rejected += 1; }
        for (const el of els) for (const n of names) pending.push([n, r.selectorText.slice(0, 80), el, pm ? '::' + pm[1] : null]); }
      if (r.cssRules && r.cssRules.length) visit(r.cssRules, scope, sel);
      continue; }
    if (!r.cssRules) continue;
    const ok = applies(r);
    if (ok === null) { containers += 1; continue; }
    if (ok) visit(r.cssRules, scope, parent); } };
  const roots = [document];
  const walk = (root) => { for (const el of root.querySelectorAll('*')) if (el.shadowRoot) { roots.push(el.shadowRoot); walk(el.shadowRoot); } };
  walk(document);
  for (const root of roots) {
    for (const sh of [...Array.from(root.styleSheets || []), ...Array.from(root.adoptedStyleSheets || [])]) {
      try { visit(sh.cssRules, root, null); } catch (e) { unreadable.push(sh.href || '(no href)'); } }
    for (const el of Array.from(root.querySelectorAll('[style]')).slice(0, 400)) {
      declare(el.style);
      for (const n of bare(el.getAttribute('style') || '')) pending.push([n, 'style=""', el, null]); } }
  for (const [href, text] of extraCss) {   // a file:// sheet Chromium will not expose, read from disk by the caller
    try { const sh = new CSSStyleSheet(); sh.replaceSync(text); visit(sh.cssRules, document, null);
          const k = unreadable.indexOf(href); if (k >= 0) unreadable.splice(k, 1); } catch (e) {} }
  for (const [name, where, el, pseudo] of pending) {
    if (empties.has(name)) continue;
    let v = getComputedStyle(el).getPropertyValue(name).trim();
    if (!v && pseudo) v = getComputedStyle(el, pseudo).getPropertyValue(name).trim();
    if (v) continue;
    const u = (undef[name] = undef[name] || {name, where: [], elements: 0}); u.elements += 1;
    if (!u.where.includes(where) && u.where.length < 3) u.where.push(where); }
  const root = getComputedStyle(document.documentElement), probe = document.createElement('span'), defined = {};
  probe.style.display = 'none'; document.documentElement.appendChild(probe);
  const resolve = (v) => { probe.style.color = ''; probe.style.color = v; return getComputedStyle(probe).color; };
  for (const [n, sys] of dsTokens) { const raw = root.getPropertyValue('--' + n).trim(); if (!raw) continue;
    defined[n] = {raw, resolved: resolve('var(--' + n + ')'), system: resolve(sys)}; }
  probe.remove();
  return {undefined: Object.values(undef), defined, unreadable, rules, containers, rejected};
}"""
# N-28 (field run 2, R2-21): what a refresh must keep from the build it refreshes. A merge dropped the header search,
# a stylesheet leak resized titles, and a phone table stopped turning into cards, while every other check passed.
JS_PARITY = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width >= 4 && r.height >= 4 && cs.visibility !== 'hidden' && cs.clip !== 'rect(0px, 0px, 0px, 0px)'; };
  const h1 = Array.from(document.querySelectorAll('h1, [role="heading"][aria-level="1"]')).find(vis);
  const t = h1 ? getComputedStyle(h1) : null;
  const lh = t ? (parseFloat(t.lineHeight) || parseFloat(t.fontSize) * 1.2) : 0;
  const inner = h1 ? h1.clientHeight - parseFloat(t.paddingTop) - parseFloat(t.paddingBottom) : 0;
  const ctrls = Array.from(document.querySelectorAll('button, input:not([type=hidden]):not([type=radio]):not([type=checkbox]), ' +
                                                     'select, [role="button"]')).filter(vis)
    .map((e) => Math.round(e.getBoundingClientRect().height)).sort((a, b) => a - b);
  const search = Array.from(document.querySelectorAll('input[type="search"], [role="search"] input, input[placeholder*="earch" i], ' +
                                                       'input[aria-label*="earch" i]')).some(vis);
  const filter = Array.from(document.querySelectorAll('select, [role="combobox"], [aria-pressed], [role="tab"], ' +
                                                       'input[type="radio"], input[type="checkbox"]')).some(vis);
  // a table restacked as labelled cards keeps its <table> but its rows stop being table rows
  const tables = Array.from(document.querySelectorAll('table')).filter(vis).map((e) => {
    const r = e.querySelector('tbody tr') || e.querySelector('tr');
    return getComputedStyle(r || e).display === (r ? 'table-row' : 'table') ? 'table' : 'cards'; });
  return {title: t ? {size: Math.round(parseFloat(t.fontSize) * 10) / 10, weight: parseInt(t.fontWeight, 10),
                      lines: Math.max(1, Math.round(inner / lh))} : null,
          control_height: ctrls.length ? ctrls[Math.floor(ctrls.length / 2)] : null, search, filter,
          table_mode: tables.length ? (tables.every((d) => d === 'table') ? 'table' : 'cards') : null};
}"""
# resolves once the page's DOM has not changed for `quietMs` (a simulated load, a late render), or at `capMs`
JS_QUIET = """([quietMs, capMs]) => (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => new Promise((done) => {
  let last = performance.now(); const start = last;
  const obs = new MutationObserver(() => { last = performance.now(); });
  obs.observe(document.documentElement, {childList: true, subtree: true, attributes: true, characterData: true});
  const tick = () => { const t = performance.now();
    if (t - last >= quietMs || t - start >= capMs) { obs.disconnect(); done(Math.round(t - start)); } else setTimeout(tick, 50); };
  setTimeout(tick, 50);
}))"""
# W47: a layout that holds at every planned width can still break between them (a heatmap cell switching from one to
# two tiles per row split "contaminants" mid-word and pushed a tag past its tile at 1200-1260 px only). Read at each
# width of the band: page overflow, words broken across lines without a hyphen, and boxed text running past its box.
JS_BAND = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 1 && r.height > 1 && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0 && cs.clip !== 'rect(0px, 0px, 0px, 0px)'; };""" + JS_PAGE_OVERFLOW + """  const midword = [], spill = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange(); let n = 0;
  // words in scripts that separate words with spaces; Chinese, Japanese or Thai text wraps between any two characters
  const WORD = /[\\p{Script=Latin}\\p{Script=Cyrillic}\\p{Script=Greek}\\u00ad]{6,}/gu;
  while (walker.nextNode() && n < 4000 && midword.length < 10) {
    const tn = walker.currentNode, el = tn.parentElement;
    if (!el || !vis(el) || getComputedStyle(el).hyphens === 'auto') continue;
    const dropcap = getComputedStyle(el, '::first-letter').float !== 'none';
    const re = new RegExp(WORD.source, 'gu'); let m;
    while ((m = re.exec(tn.textContent)) && n < 4000) {
      n += 1;
      if (m[0].includes('\\u00ad')) continue;   // a soft hyphen is a break the author allowed
      if (dropcap && !tn.textContent.slice(0, m.index).trim()) continue;   // a floated first letter sits beside its word
      range.setStart(tn, m.index); range.setEnd(tn, m.index + m[0].length);
      const tops = new Set(Array.from(range.getClientRects()).filter((r) => r.width > 0).map((r) => Math.round(r.top)));
      if (tops.size > 1) { midword.push({word: m[0], el: label(el)}); break; }
    }
  }
  // a box: a background (colour or image), a shadow, or a border. Its in-flow content running past its edges is spill;
  // an absolutely placed badge, an invisible tooltip or a full-bleed negative margin is placed there on purpose
  const boxed = (cs) => cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.backgroundImage !== 'none' || cs.boxShadow !== 'none'
    || ['Top', 'Right', 'Bottom', 'Left'].some((k) => parseFloat(cs['border' + k + 'Width']) > 0);
  const inflow = (c) => { const cs = getComputedStyle(c); return cs.position !== 'absolute' && cs.position !== 'fixed'
    && parseFloat(cs.marginLeft) >= 0 && parseFloat(cs.marginRight) >= 0 && vis(c); };
  // content a region inside the view really scrolls sideways (a wide data table) is reachable there, not spilled; the
  // region around the view is the page's own scroller, and what runs past it is page overflow (R2-27)
  const scrolled = (e) => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
    if (viewScrollers.includes(a)) continue;
    const o = getComputedStyle(a).overflowX;
    if ((o === 'auto' || o === 'scroll') && a.scrollWidth > a.clientWidth + 1) return true; } return false; };
  // hidden by an ancestor (a visually hidden header row: a 1 px clipped thead) is not seen, so it cannot spill
  const hiddenBy = (e) => { for (let a = e; a && a !== document.body; a = a.parentElement) {
    const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
    if (cs.clip === 'rect(0px, 0px, 0px, 0px)' || /inset\\(50%\\)/.test(cs.clipPath)
        || ((r.width <= 1 || r.height <= 1) && cs.overflow !== 'visible')) return true; } return false; };
  // content that a clipping or scrolling element inside the box holds (a scrollable tab strip) stays inside it
  const held = (c, b) => { for (let a = c.parentElement; a && a !== b; a = a.parentElement)
    if (getComputedStyle(a).overflowX !== 'visible') return true; return false; };
  const ROWS = ['table-row', 'table-row-group', 'table-header-group', 'table-footer-group', 'table-column', 'table-column-group'];
  let boxes = 0;
  for (const b of document.querySelectorAll('body *')) {
    if (spill.length >= 10 || boxes >= 600) break;
    const cs = getComputedStyle(b);
    if (cs.overflowX !== 'visible' || ROWS.includes(cs.display) || !boxed(cs) || !vis(b) || !b.textContent.trim()) continue;
    boxes += 1;
    if (scrolled(b) || hiddenBy(b)) continue;
    const br = b.getBoundingClientRect(); let over = 0;
    for (const nd of b.childNodes) if (nd.nodeType === 3 && nd.textContent.trim()) {
      range.selectNodeContents(nd);
      for (const r of range.getClientRects()) over = Math.max(over, r.right - br.right, br.left - r.left); }
    let k = 0;
    for (const c of b.querySelectorAll('*')) { if (++k > 150) break;
      if (!inflow(c) || !Array.from(c.childNodes).some((x) => x.nodeType === 3 && x.textContent.trim()) || held(c, b)) continue;
      const r = c.getBoundingClientRect(); over = Math.max(over, r.right - br.right, br.left - r.left); }
    if (over > 1) spill.push({el: label(b), px: Math.round(over), text: b.textContent.trim().slice(0, 40)});
  }
  // a select shows its value as no text node, so no text check sees it cut. A fresh select holding one option's label,
  // with the select's own font, spacing, padding, border, box and appearance pinned and sized to its content, says how
  // wide it must be. It sits in a closed shadow root on the document, so no page rule (a sibling or :only-child rule, an
  // !important width) reaches it and no observer of the app's containers sees it. Read for the value shown and for the
  // longest option a user can pick; on the box, not clientWidth, which rounds (field run W55, W57; review I1)
  const cut = [], present = []; let cutNote = '';
  if (!(window.CSS && CSS.supports('field-sizing', 'content'))) cutNote = 'this browser cannot size a select to its content';
  else {
    const canvas = document.createElement('canvas').getContext('2d');
    const host = document.createElement('div');
    for (const [k, v] of [['display', 'block'], ['position', 'absolute'], ['left', '-99999px'], ['top', '0'], ['visibility', 'hidden']])
      host.style.setProperty(k, v, 'important');
    const root = host.attachShadow({mode: 'closed'}); document.documentElement.appendChild(host);
    const PIN = ['font-family', 'font-size', 'font-weight', 'font-style', 'font-stretch', 'font-variant', 'font-feature-settings',
      'font-variation-settings', 'font-optical-sizing', 'font-size-adjust', 'font-synthesis', 'font-kerning', 'text-rendering',
      'letter-spacing', 'word-spacing', 'text-transform', 'text-indent', 'padding-left', 'padding-right',
      'border-left-width', 'border-left-style', 'border-right-width', 'border-right-style', 'box-sizing', 'appearance'];
    const need = (s, cs, text) => {
      const probe = document.createElement('select'); probe.appendChild(new Option(text));
      for (const k of PIN) probe.style.setProperty(k, cs.getPropertyValue(k), 'important');
      probe.style.setProperty('field-sizing', 'content', 'important');
      root.appendChild(probe); const w = parseFloat(getComputedStyle(probe).width); probe.remove(); return w; };
    let probed = 0;
    for (const s of document.querySelectorAll('select')) {
      if (s.multiple || s.size > 1 || !s.options.length || !s.checkVisibility() || !vis(s) || hiddenBy(s)) continue;
      if (s.id) present.push('select#' + s.id);   // where an id'd select exists decides a shell finding (review IB)
      if (cut.length >= 10) continue;
      if (probed >= 40) { cutNote = 'more than 40 selects: the rest were not measured'; continue; }
      probed += 1;
      const cs = getComputedStyle(s); canvas.font = cs.font;
      const shown = s.selectedIndex; let longest = Math.max(0, shown), best = -1;
      for (let i = 0; i < s.options.length; i++) {
        const o = s.options[i];
        if (i !== shown && (o.hidden || o.matches(':disabled'))) continue;   // a placeholder, or a disabled group
        const w = canvas.measureText(o.label).width; if (w > best) { best = w; longest = i; } }
      // the used width, like the probe's: an ancestor's zoom or scale changes neither (review IA)
      const have = parseFloat(cs.width);
      // a select sized to its value (field-sizing: content) is as wide as the option chosen, up to its max-width: read it
      // with that option chosen, then put its value back. No event fires, though both options stay dirty for this load
      // (a later change to their `selected` attribute is ignored). An ancestor that clips the grown select is not read
      // here: which one clips depends on positioning, direction and overflow propagation, and a guess brought back false
      // cuts (W63; batch 18 review S4, and round 2's I1, which reverted S9)
      const sized = cs.getPropertyValue('field-sizing') === 'content';
      for (const i of new Set([shown, longest].filter((i) => i >= 0))) {   // -1: it shows nothing
        const want = need(s, cs, s.options[i].label);
        let box = have;
        if (sized && i !== shown) { s.selectedIndex = i; box = parseFloat(getComputedStyle(s).width); s.selectedIndex = shown; }
        if (box < want - 0.5) {
          cut.push({el: label(s), px: Math.round(want - box), text: s.options[i].label.trim().slice(0, 40), shown: i === shown});
          break;
        }
      }
    }
    host.remove();
  }
  return {overflow, overflow_in: overflowIn, midword, spill, cut, cut_note: cutNote, selects: present};
}"""
STEP_FIELDS = ("goto", "click", "fill", "press", "select", "expect_visible", "expect_hidden", "expect_text",
               "expect_no_text", "expect_count",
               "expect_disabled", "expect_enabled", "expect_route", "expect_focus", "expect_in_viewport",
               "expect_reachable", "reload",
               "screenshot", "axe")


def axe_path() -> Path:
    return Path(os.environ.get("PDG_AXE_PATH") or PKG_ROOT / "vendor" / "axe-core" / "axe.min.js")


def _height(vw: int) -> int:
    return 844 if vw < 600 else (1024 if vw < 1200 else 900)


def _url(entry: Path, route: str | None) -> str:
    base = entry.resolve().as_uri()
    if not route:
        return base
    if route.startswith("?"):
        q, _, h = route.partition("#")
        return base + q + ("#" + h if h else "")
    return base + (route if route.startswith("#") else "#" + route)


class Collector:
    def __init__(self) -> None:
        self.console: list[dict[str, Any]] = []
        self.requests: list[str] = []

    def attach(self, page, where: str) -> None:
        page.on("console", lambda m: self.console.append({"where": where, "text": m.text[:300]}) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.console.append({"where": where, "text": f"pageerror: {e}"[:300]}))

        def route(r):
            url = r.request.url
            if url.startswith(ALLOWED_SCHEMES):
                r.continue_()
            else:
                self.requests.append(f"{where}: {url[:160]}")
                r.abort()
        page.route("**/*", route)


def _axe(page, tags: list[str]) -> list[dict[str, Any]]:
    if not page.evaluate("() => typeof window.axe !== 'undefined'"):
        page.add_script_tag(path=str(axe_path()))
    out = page.evaluate("""async (tags) => { const r = await axe.run(document, {runOnly: {type: 'tag', values: tags},
        resultTypes: ['violations']}); return r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help,
        nodes: v.nodes.slice(0, 5).map(n => ({target: n.target.join(' '), summary: (n.failureSummary || '').slice(0, 300)}))})); }""", tags)
    return out


def _settle(page) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(120)


def _step_fields(step: dict[str, Any]) -> list[str]:
    return [k for k in STEP_FIELDS if step.get(k) is not None]


def _run_step(page, step: dict[str, Any], entry: Path, timeout: int, shots: Path, label: str, tags: list[str],
              axe_hits: list[dict[str, Any]]) -> None:
    unknown = sorted(set(step) - set(STEP_FIELDS))
    active = _step_fields(step)
    if unknown:
        raise AssertionError(f"unknown scenario step field(s): {', '.join(unknown)}")
    if len(active) != 1:
        got = ", ".join(active) if active else "none"
        raise AssertionError(f"scenario step must set exactly one action/expectation field; got {len(active)} ({got})")
    action = active[0]
    if action == "goto":
        url = _url(entry, step["goto"])
        if unquote(page.url) == unquote(url):
            # a link to the page the user is on does nothing in a browser (no load, no hashchange, no focus move), so the
            # next check would measure from wherever the last step left off. A goto means "arrive": at the top, with
            # focus and the Tab order starting over; the app's state is kept, as every later goto keeps it (W50)
            page.evaluate(JS_ARRIVE)
        else:
            page.goto(url)
        _settle(page)
    elif action == "click":
        page.locator(step["click"]).first.click(timeout=timeout)
        page.wait_for_timeout(80)
    elif action == "fill":
        sel, text = step["fill"]
        page.locator(sel).first.fill(text, timeout=timeout)
    elif action == "press":
        page.keyboard.press(step["press"])
        page.wait_for_timeout(60)
    elif action == "select":
        sel, val = step["select"]
        page.locator(sel).first.select_option(val, timeout=timeout)
    elif action in ("expect_visible", "expect_hidden"):
        sel, want = step[action], action[len("expect_"):]
        try:
            page.locator(sel).first.wait_for(state=want, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - say what the page shows, not only that the wait ran out (R2-19)
            try:
                loc = page.locator(sel)
                n = loc.count()
                shown = sum(1 for i in range(min(n, 20)) if loc.nth(i).is_visible())
            except Exception:  # noqa: BLE001 - the page went away mid-report: keep the original error
                raise exc from None
            if not n:
                now_ = "not on the page"
            elif want == "hidden":
                now_ = "still visible" + (f" (the first of {n} matches; {shown} visible)" if n > 1 else "")
            elif shown:   # the step waits on the first match, which is hidden while another copy shows (R2-11)
                now_ = (f"matched {n} times; the first match is hidden and {shown} other(s) are visible, so scope the "
                        "selector to the one the user sees")
            else:
                now_ = f"on the page but not visible ({n} match{'es' if n != 1 else ''}, none visible)"
            raise AssertionError(f"{sel} is {now_} after {timeout / 1000:g} s (expected {want})") from None
    elif action == "expect_text":
        sel, sub = step["expect_text"]
        loc = page.locator(sel).first
        loc.wait_for(state="attached", timeout=timeout)
        txt = loc.inner_text(timeout=timeout)
        if sub not in txt:
            raise AssertionError(f"{sel} text {txt[:80]!r} does not contain {sub!r}")
    elif action == "expect_no_text":
        # a "never shows X" acceptance (field run 2, R2-04): the selector matches, and none of its matches shows the
        # substring. A selector matching nothing fails: a screen that never rendered shows nothing (R2-07)
        sel, sub = step["expect_no_text"]
        loc = page.locator(sel)
        try:
            loc.first.wait_for(state="attached", timeout=timeout)
        except Exception:  # noqa: BLE001 - nothing to read is the failure (audit #10)
            raise AssertionError(f"{sel} matched nothing, so it cannot show that {sub!r} is absent: check a container "
                                 "that always renders") from None
        hit = next((x for x in loc.all_inner_texts() if sub in x), None)
        if hit is not None:
            raise AssertionError(f"{sel} still shows {sub!r}: {hit[:80]!r}")
    elif action == "expect_count":
        sel, n = step["expect_count"]
        got = page.locator(sel).count()
        if got != int(n):
            raise AssertionError(f"{sel}: {got} elements, expected {n}")
    elif action == "expect_disabled":
        if not page.locator(step["expect_disabled"]).first.is_disabled(timeout=timeout):
            raise AssertionError(f"{step['expect_disabled']} is enabled, expected disabled")
    elif action == "expect_enabled":
        if not page.locator(step["expect_enabled"]).first.is_enabled(timeout=timeout):
            raise AssertionError(f"{step['expect_enabled']} is disabled, expected enabled")
    elif action == "expect_route":
        h = page.evaluate("() => location.hash")
        if h != step["expect_route"]:
            raise AssertionError(f"route {h!r}, expected {step['expect_route']!r}")
    elif action == "expect_focus":
        if not page.evaluate("(s) => !!document.activeElement && document.activeElement.matches(s)", step["expect_focus"]):
            raise AssertionError(f"focus is not on {step['expect_focus']}")
    elif action == "expect_reachable":
        # a completing action a user can find from where they are: within one screen of scrolling (backlog N-18). The
        # click itself always passes, since Playwright scrolls to its target
        loc = page.locator(step["expect_reachable"]).first   # any selector `click` accepts (audit #9)
        loc.wait_for(state="attached", timeout=timeout)
        if not loc.evaluate(JS_REACHABLE):
            raise AssertionError(f"{step['expect_reachable']} is more than one screen away from where the user is")
    elif action == "expect_in_viewport":
        sel = step["expect_in_viewport"]
        why = page.evaluate(JS_IN_VIEW, page.locator(sel).first.element_handle(timeout=timeout))
        if why:
            raise AssertionError(f"{sel} is not in view without scrolling: {why}")
    elif action == "reload":
        page.reload()
        _settle(page)
    elif action == "screenshot":
        page.screenshot(path=str(shots / f"{label}-{step['screenshot']}.png"), full_page=True)
    elif action == "axe":
        for v in _axe(page, tags):
            axe_hits.append({**v, "where": f"{label}:{step['axe']}"})


# a screen marker a user can see: a box, not hidden, not transparent (itself or an ancestor; Playwright's "visible"
# counts opacity 0), and not a link, button or navigation entry that names a screen to highlight it (W52 review I1)
JS_SHOWN_SCREENS = """() => {
  const seen = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0
    && (!e.checkVisibility || e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})); };
  const shown = new Set(), present = new Set(), linked = new Set();
  for (const el of document.querySelectorAll('[data-screen]')) {
    if (el.closest('a, button, nav, [role="navigation"]')) { linked.add(el.getAttribute('data-screen')); continue; }
    const id = el.getAttribute('data-screen');
    present.add(id);
    // a display: contents wrapper has no box of its own: what it holds is the screen
    if (seen(el) || (getComputedStyle(el).display === 'contents' && [...el.querySelectorAll('*')].some(seen))) shown.add(id);
  }
  return {shown: [...shown], present: [...present], linked: [...linked]};
}"""
JS_SHOWS_SCREEN = "(id) => (" + JS_SHOWN_SCREENS + ")().shown.includes(id)"
# the visible single selects whose longest option a user can pick is not the one chosen: where, and which option; and
# how many single selects the screen hides (W58)
JS_SELECTS = """() => {
  const label = """ + JS_LABEL + """;
  const canvas = document.createElement('canvas').getContext('2d'), out = []; let hidden = 0;
  [...document.querySelectorAll('select')].forEach((s, index) => {
    // the screen being read only (a single-file app keeps its other screens hidden), and a select a user can change
    const view = s.closest('[data-screen]');
    if (s.multiple || s.size > 1 || !s.options.length || s.disabled || (view && !view.checkVisibility())) return;
    const r = s.getBoundingClientRect();
    if (!s.checkVisibility() || r.width <= 1 || r.height <= 1) { hidden += 1; return; }
    canvas.font = getComputedStyle(s).font; let best = -1, longest = -1;
    for (let k = 0; k < s.options.length; k++) {
      const o = s.options[k]; if (o.hidden || o.matches(':disabled')) continue;
      const w = canvas.measureText(o.label).width; if (w > best) { best = w; longest = k; } }
    if (longest < 0 || longest === s.selectedIndex) return;
    out.push({index, id: s.id, el: label(s), longest, text: s.options[longest].label.trim().slice(0, 40)});
  });
  return {picks: out, hidden};
}"""
# a disclosure a user opens to reach a select: a visible control with aria-expanded="false" whose aria-controls region
# holds one, or the summary of a closed <details> that does; one named in `skip` was opened already (W58, D-214)
# a live count in brackets ("Filters (2)") is left out: the name is part of a finding's identity (review N3); other
# numbers stay, so "Group 1" and "Group 2" are two disclosures (review S-a)
JS_TOGGLE_NAME = """(b) => (""" + JS_LABEL + """)(b) + " '" + (b.textContent || '').replace(/\\s*[([]\\d+[)\\]]/g, '').trim()
  .replace(/\\s+/g, ' ').slice(0, 30) + "'" """
JS_SELECT_TOGGLE = """(skip) => {
  const name = """ + JS_TOGGLE_NAME + """;
  for (const b of document.querySelectorAll('[aria-expanded="false"][aria-controls], details:not([open]) > summary')) {
    const regions = b.tagName === 'SUMMARY' ? [b.parentElement]
      : b.getAttribute('aria-controls').split(/\\s+/).map((i) => document.getElementById(i)).filter(Boolean);
    if (b.checkVisibility() && regions.some((r) => r.querySelector('select')) && !skip.includes(name(b))) return b; }
  return null;
}"""
# R2-26: a list marked its chosen row with the worst score band's own alert fill, turned that row's score box white (the
# band vanished from the row being read) and hovered rows in the lowest band's grey; every gate passed. A group is an
# item marked current, selected or pressed and its resting siblings of the same tag and first class. The status colours
# are the design system's (by role, from the caller) and any fill that varies across the resting items' marks: a colour
# that encodes data. A mark is a descendant with a fill of its own, named by its position in its item, so a current item
# and a resting one built from one template pair up whatever their classes (review I6). `window.__pdgRest` keeps each
# group's first resting item and `window.__pdgRestMarks` its marks, for the hover
JS_FILL = """(() => { const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  // every CSS colour as the screen shows it in sRGB (color-mix, oklch and lab compute to other notations; review S3)
  const norm = (s) => { if (!s || s === 'transparent' || s === 'rgba(0, 0, 0, 0)') return 'rgba(0, 0, 0, 0)';
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data;
    return a === 0 ? 'rgba(0, 0, 0, 0)' : a === 255 ? 'rgb(' + r + ', ' + g + ', ' + b + ')'
      : 'rgba(' + r + ', ' + g + ', ' + b + ', ' + Math.round(a / 2.55) / 100 + ')'; };
  return (e) => norm(getComputedStyle(e).backgroundColor); })()"""
JS_MARKS = """(item, own, fill) => { const out = [], els = [];
  // its place from the first child and from the last: an extra element at the front of the current item (the "where
  // you are" bar) shifts one, not the other (review S9)
  const path = (d, end) => { const p = []; for (let x = d; x !== item; x = x.parentElement) { const sib = [...x.parentElement.children];
    p.unshift(end ? sib.length - 1 - sib.indexOf(x) : sib.indexOf(x)); } return d.tagName.toLowerCase() + (end ? '@-' : '@') + p.join('/'); };
  for (const d of item.querySelectorAll('*')) {
    if (out.length >= 40) break;
    const f = fill(d);
    if (!d.checkVisibility() || f === 'rgba(0, 0, 0, 0)' || (!own && f === fill(item))) continue;
    out.push({key: path(d, false), alt: path(d, true), el: LABEL(d), cls: [...d.classList], fill: f}); els.push(d); }
  return [out, els]; }"""
JS_STATE_GROUPS = """(status) => {
  const clear = (c) => c === 'rgba(0, 0, 0, 0)';
  const fill = """ + JS_FILL + """;
  const LABEL = """ + JS_LABEL + """;
  const marks = """ + JS_MARKS + """;
  const probe = document.createElement('div'); document.body.appendChild(probe);
  const fills = {};
  for (const [name, hex] of Object.entries(status)) { probe.style.backgroundColor = ''; probe.style.backgroundColor = hex;
    if (probe.style.backgroundColor) { const k = fill(probe); fills[k] = (fills[k] || []).concat([name]); } }
  probe.remove();
  // what is behind an item, as seen: every fill above it blended down onto white, a translucent one too (review I2)
  const surface = (e) => { const layers = []; for (let a = e.parentElement; a; a = a.parentElement) layers.unshift(fill(a));
    let c = [255, 255, 255];
    for (const l of layers) { const n = (l.match(/[\\d.]+/g) || []).map(Number); const al = n.length > 3 ? n[3] : 1;
      if (!clear(l)) c = c.map((v, k) => al * n[k] + (1 - al) * v); }
    return 'rgb(' + c.map(Math.round).join(', ') + ')'; };
  // marked for assistive technology, or by the class names a build commonly marks it with
  const CUR = '[aria-current]:not([aria-current="false"]), [aria-selected="true"], [aria-pressed="true"], '
    + '.active, .selected, .is-active, .is-selected, .current, .is-current, .router-link-exact-active';
  // one kind of item: no classes on either, or a class they share that is not a state class ("is-selected row" and
  // "row" are one list; a badge marked `active` beside a date is not; review S1, part 2 review S5)
  const STATE = /^(active|selected|current|is-active|is-selected|is-current|router-link-active|router-link-exact-active)$/;
  const own = (e) => [...e.classList].filter((k) => !STATE.test(k));
  const kind = (s, c) => own(c).length ? own(c).some((k) => s.classList.contains(k)) : !own(s).length;   // review S8
  const groups = [], seen = new Set(); window.__pdgRest = []; window.__pdgRestMarks = [];
  for (const c of document.querySelectorAll(CUR)) {
    if (groups.length >= 12 || !c.parentElement || seen.has(c.parentElement) || !c.checkVisibility()) continue;
    // siblings of one kind: a badge marked `active` beside a date is not a list (review S1)
    const rest = [...c.parentElement.children].filter((s) => s !== c && s.tagName === c.tagName && kind(s, c)
      && s.checkVisibility() && !s.matches(CUR));
    if (!rest.length) continue;
    seen.add(c.parentElement);
    const byKey = {}, data = {};
    for (const s of rest.slice(0, 30)) for (const m of marks(s, false, fill)[0]) {
      const b = byKey[m.key] = byKey[m.key] || {fills: new Set(), cls: null, alts: new Set()};
      b.fills.add(m.fill); b.alts.add(m.alt);
      b.cls = b.cls === null ? new Set(m.cls) : new Set([...b.cls].filter((k) => m.cls.includes(k))); }
    // a place whose marks share a class, or sit at the same place from both ends in every item (review S10, S12)
    for (const [k, b] of Object.entries(byKey))
      if (b.fills.size > 1 && (b.cls.size || b.alts.size === 1)) for (const f of b.fills) data[f] = data[f] || k.split('@')[0];
    // the item hovered and clicked is one a user can press: a workflow's later steps are disabled until the current is
    // done, and a click on one waited out its time and left the list unjudged (refresh field run, stepper tabs)
    const off = (s) => s.matches(':disabled, [aria-disabled="true"]');
    const pick = rest.find((s) => !off(s)) || rest[0];
    const [restMarks, restEls] = marks(pick, false, fill);
    window.__pdgRest.push(pick); window.__pdgRestMarks.push(restEls);
    groups.push({el: LABEL(c), list: LABEL(c.parentElement), surface: surface(c), current: fill(c),
                 cls: [...c.classList], rest_cls: [...pick.classList],
                 current_marks: marks(c, true, fill)[0], rest: fill(pick), rest_fills: [...new Set(rest.map(fill))],
                 rest_marks: restMarks, data, rest_link: !!(pick.closest('a[href], nav, [role=navigation]') || pick.querySelector('a[href]')),
                 rest_disabled: off(pick),
                 rest_text: (pick.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60), rest_el: LABEL(pick)});
  }
  return {groups, status: fills};
}"""
# the resting item and the same marks, read again (after the pointer moved onto it)
JS_ITEM = """(i) => { const fill = """ + JS_FILL + """;
  const e = window.__pdgRest[i], ms = window.__pdgRestMarks[i];
  if (!e.isConnected || ms.some((d) => !d.isConnected)) return {redrawn: true};   // no longer what was read (review I8)
  return {fill: fill(e), marks: ms.map((d) => fill(d))}; }"""
# R2-29: a list redrawn on selection that put focus back on the new row by script showed the stakeholder a focus ring on
# what he had clicked. After a click on a resting item: is focus on a copy of it that replaced it (at the same place, or
# the same tag, first class and text), and does a control in the list (not a text field, which always shows its ring)
# match :focus-visible. Focus that left the list (a detail heading, a dialog) is a documented pattern, not judged here
JS_CLICK_MARK = """(i) => { const e = window.__pdgRest[i]; const r = e.getBoundingClientRect();
  window.__pdgClicked = e; window.__pdgClickList = e.parentElement; window.__pdgClickBox = [r.left, r.top, r.height];
  window.__pdgClickHTML = e.outerHTML; }"""
JS_CLICKED = """() => { const e = window.__pdgClicked, a = document.activeElement;
  const label = """ + JS_LABEL + """;
  const STATE = /^(active|selected|current|is-active|is-selected|is-current|router-link-active|router-link-exact-active)$/;
  const kin = (x) => x.tagName + '.' + [...x.classList].filter((k) => !STATE.test(k)).sort().join('.')
    + '|' + (x.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
  const idle = !a || a === document.body || a === document.documentElement;
  // a copy: the node of the clicked item's tag that holds focus, of its kind or in its box (within 4 px, its height
  // within 1.5 times): a detail region that took the list's place, and its heading, are not (review I-B)
  const row = idle ? null : a.closest(e.tagName.toLowerCase()), box = window.__pdgClickBox;
  const r = row && row.getBoundingClientRect();
  const samePlace = !!r && Math.abs(r.left - box[0]) <= 4 && Math.abs(r.top - box[1]) <= 4 && r.height <= box[2] * 1.5
    && r.height * 1.5 >= box[2];
  const own = (x) => [...x.classList].filter((k) => !STATE.test(k));
  const sameKind = !!row && (own(e).length ? own(e).some((k) => row.classList.contains(k)) : !own(row).length);
  const copy = !e.isConnected && !!row && (kin(row) === kin(e) || samePlace && sameKind);   // part 2 final review
  const list = window.__pdgClickList;
  const inList = !idle && (a === e || e.contains(a) || copy || (list.isConnected && list.contains(a)));
  const typing = !idle && (a.isContentEditable || a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT'
    && !/^(checkbox|radio|button|submit|reset|image|range|color|file)$/i.test(a.type)));
  return {connected: e.isConnected, on_it: !idle && (a === e || e.contains(a)), copy, in_list: inList,
          ring: inList && !typing && a.matches(':focus-visible'), active: idle ? '' : label(a)}; }"""
JS_CLICK_SETTLED = """(capMs) => new Promise((done) => {
  const start = performance.now();
  const tick = () => {
    const e = window.__pdgClicked, list = window.__pdgClickList, a = document.activeElement;
    const changed = !e || !e.isConnected || e.outerHTML !== window.__pdgClickHTML;
    const focused = a && a !== document.body && a !== document.documentElement && e && a !== e && !e.contains(a)
      && list && list.isConnected && list.contains(a);
    if (changed || focused || performance.now() - start >= capMs) done(true); else setTimeout(tick, 50);
  };
  tick();
})"""
# every transition and animation that ends has ended, or 1 s: a looping one (a spinner) is not waited for (review S4)
JS_SETTLED = """() => Promise.race([Promise.all(document.getAnimations().filter((a) => {
    const t = a.effect && a.effect.getComputedTiming(); return t && Number.isFinite(t.endTime); })
  .map((a) => a.finished.catch(() => null))), new Promise((r) => setTimeout(r, 1000))]).then(() => true)"""
JS_HASH_LINKS = "() => [...new Set([...document.querySelectorAll('a[href^=\"#/\"]')].map((a) => a.getAttribute('href')))]"
_VISIBLE_TEXT_JS = """(word) => {
  const re = new RegExp(word, 'i');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const el = walker.currentNode.parentElement;
    if (!el || !re.test(walker.currentNode.textContent)) continue;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) continue;
    const r = el.getBoundingClientRect();
    if (r.width >= 4 && r.height >= 4) return (el.innerText || el.textContent).trim().slice(0, 160);
  }
  return null;
}"""


def visible_text_with(entry: Path, word: str, timeout_ms: int = 3000) -> tuple[bool, str] | None:
    """Whether a sighted user sees `word` on the entry page once it has rendered (scripts included), and the text found.
    Offline like the suite (non-local requests aborted). None when no browser is available, so callers can fall back."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(ALLOWED_SCHEMES) else r.abort())
                page.goto(_url(entry, None), wait_until="load")
                try:
                    handle = page.wait_for_function(_VISIBLE_TEXT_JS, arg=word, timeout=timeout_ms)
                    return True, str(handle.json_value())
                except Exception:  # noqa: BLE001 - not shown within the timeout
                    return False, ""
            finally:
                browser.close()
    except Exception:  # noqa: BLE001 - Chromium missing or failing to start: no rendered answer
        return None


def _core(route: str) -> str:
    return route.split("#", 1)[-1].strip("/")


def rendered_screens(entry: Path, routes: dict[str, str], others: dict[str, str] | None = None, timeout_ms: int = 3000,
                     budget_s: float = 30.0) -> dict[str, set[str]] | None:
    """Which of `routes` (screen id → route) show their own screen on a cold load: the runtime answer when a build writes
    its markers from data (`data-screen="feed-${id}"`), which no text scan can read (W52). A marker counts when a user
    can see it and it is not a link, button or navigation entry; and it must be absent from at least one other route
    loaded (another missing screen's, or one of `others`), or the route does not choose it. Offline like the suite.
    Returns {"shown", "everywhere", "hidden", "linked", "unloaded", "unchecked"}; None when no browser is available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    out: dict[str, set[str]] = {k: set() for k in ("shown", "everywhere", "hidden", "linked", "unloaded", "unchecked")}
    seen_on: dict[str, set[str]] = {}          # route → the screens it shows
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                def fresh():
                    pg = browser.new_page(viewport={"width": 1280, "height": 900})
                    pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(ALLOWED_SCHEMES) else r.abort())
                    return pg

                def load(page, route: str, wait_for: str | None):
                    """The page after loading `route` cold, and what it shows; (a fresh page, None) when it does not load."""
                    try:
                        page.goto("about:blank")
                        page.goto(_url(entry, route), wait_until="load", timeout=3 * timeout_ms)
                    except Exception:  # noqa: BLE001 - a route that never finishes loading: say so, keep going (S1)
                        page.close()
                        return fresh(), None
                    try:
                        if wait_for is not None:
                            page.wait_for_function(JS_SHOWS_SCREEN, arg=wait_for, timeout=timeout_ms)
                        else:
                            _settle(page)
                    except Exception:  # noqa: BLE001 - not shown within the timeout
                        pass
                    return page, page.evaluate(JS_SHOWN_SCREENS)

                page, deadline = fresh(), time.monotonic() + budget_s
                for sid, route in routes.items():
                    if time.monotonic() > deadline:
                        out["unchecked"].add(sid)
                        continue
                    page, snap = load(page, route, sid)
                    if snap is None:
                        out["unloaded"].add(sid)
                        continue
                    seen_on[route] = set(snap["shown"])
                    if sid not in snap["shown"] and sid in snap["present"]:
                        out["hidden"].add(sid)
                    elif sid not in snap["present"] and sid in snap["linked"]:
                        out["linked"].add(sid)
                candidates = [s for s in routes if s in seen_on.get(routes[s], set())]
                # "every route" takes 3 routes, as in the sweep: a list shown beside its record is on 2 of them. Fill up
                # with other screens' routes, none nested in a candidate's
                mine = {_core(routes[s]) for s in candidates}
                ctrl = [r for r in (others or {}).values() if r not in seen_on and not any(
                    _core(r).startswith(m + "/") or m.startswith(_core(r) + "/") for m in mine if m)]
                for r in ctrl:
                    if not candidates or len(seen_on) >= 3 or time.monotonic() > deadline:
                        break
                    page, snap = load(page, r, None)
                    if snap is not None:
                        seen_on[r] = set(snap["shown"])
                for sid in candidates:
                    elsewhere = [shown for r, shown in seen_on.items() if r != routes[sid]]
                    if len(elsewhere) >= 2 and all(sid in shown for shown in elsewhere):
                        out["everywhere"].add(sid)
                    else:
                        out["shown"].add(sid)
                return out
            finally:
                browser.close()
    except Exception:  # noqa: BLE001 - Chromium missing or failing to start: no rendered answer
        return None


def _everywhere(rep: dict[str, Any], vw: int) -> None:
    """A screen whose marker every other route shows too was not chosen by its own route (navigation links or screens
    stacked on one page): its route does not render it. Needs 3 routes, so a list shown beside its record is no case
    (W52 review I1)."""
    rows = [r for r in rep["screens"] if r["viewport"] == vw and "shows" in r]
    if len({r["route"] for r in rows}) < 3:
        return
    for r in rows:
        others = [o for o in rows if o["route"] != r["route"]]
        if r["renders_screen"] and all(r["screen"] in o["shows"] for o in others):
            r.update(renders_screen=False, renders_why="its marker shows on every route")


def _label(el: dict[str, Any]) -> str:
    bits = [el.get("tag") or "element"]
    if el.get("id"):
        bits.append(f"#{el['id']}")
    if el.get("cls"):
        bits.append("." + ".".join(str(el["cls"]).split()[:2]))
    text = el.get("text")
    return "".join(bits) + (f" '{text}'" if text else "")


def _clip_key(x: dict[str, Any]) -> tuple:
    return (x.get("tag"), x.get("id"), x.get("cls"), (x.get("text") or "")[:40])


def _clip_px(x: dict[str, Any]) -> tuple[int, int]:
    return x.get("scrollW", 0) - x.get("clientW", 0), x.get("scrollH", 0) - x.get("clientH", 0)


def _spacing_clips(after: dict[str, Any], before: tuple[int, int] | None) -> bool:
    """Does the 1.4.12 spacing cause this clipping? Lines of text newly or further clipped, yes (a clamped row title
    loses lines). A single-line truncation by design, such as an ellipsis, clips with or without the spacing, so only a
    new horizontal clip counts (independent audit #3)."""
    ax, ay = _clip_px(after)
    bx, by = before if before is not None else (0, 0)
    return ay > max(by, 0) + 1 or (bx <= 1 and ax > 1)


def _focus_obscured(page, limit: int) -> list[dict[str, Any]]:
    hidden: list[dict[str, Any]] = []
    for key in ("Tab", "Shift+Tab"):
        page.evaluate(JS_RESET_FOCUS)
        seen = set()
        for _ in range(limit):
            page.keyboard.press(key)
            page.wait_for_timeout(10)
            f = page.evaluate(JS_FOCUS_OBSCURED)
            if not f:
                continue
            uid = f"{key}:{f['uid']}"
            if uid in seen:
                break
            seen.add(uid)
            if f["hidden"]:
                hidden.append({**f, "direction": key})
    return hidden


def _forbidden(page, forbidden: list[str] | None, where: str, vw: int, rep: dict[str, Any]) -> None:
    """The plan's forbidden text on the page just opened: one innerText read (field run 2, R2-04)."""
    if not forbidden:
        return
    text = page.inner_text("body")
    rep["forbidden_text"] += [{"where": where, "viewport": vw, "text": f} for f in forbidden if f in text]


_TARGET_STEPS = ("click", "fill", "select", "expect_visible", "expect_hidden", "expect_text", "expect_no_text",
                 "expect_count", "expect_disabled", "expect_enabled", "expect_focus", "expect_in_viewport",
                 "expect_reachable")


def _match_report(page, step: dict[str, Any]) -> str:
    """What a failing step's selector matched, so the fix goes to the plan when the selector is wrong: a click on a
    first match that is hidden (another tab's copy) timed out with no hint, and a builder rewrote the page's text instead
    (field run 2, R2-11)."""
    action = next((k for k in _TARGET_STEPS if step.get(k) is not None), None)
    if action is None:
        return ""
    sel = step[action][0] if isinstance(step[action], list) else step[action]
    try:
        loc = page.locator(sel)
        n = loc.count()
        if not n:
            return f" [{sel} matched nothing]"
        visible = [i + 1 for i in range(min(n, 12)) if loc.nth(i).is_visible()]
        hint = ("; the step uses the first match, which is hidden: scope the selector in the plan"
                if action in ("click", "fill", "select") and visible and visible[0] != 1 else "")
        return f" [{sel} matched {n}; visible: {', '.join(map(str, visible)) or 'none'}{hint}]"
    except Exception:  # noqa: BLE001 - a report about the failure must never fail itself
        return ""


def _tiles(page, shots: Path, name: str, vw: int, limit: int = 8) -> int:
    """At phone widths, viewport-height tiles of a tall page: a full-page screenshot at 390 px is too small to read, so
    a reviewer cropped them by hand (backlog N-08)."""
    if vw > 480:
        return 0
    vh = _height(vw)
    height = page.evaluate("() => document.documentElement.scrollHeight")
    if height <= vh * 1.2:
        return 0
    n = min(limit, -(-height // vh))
    for i in range(n):
        page.evaluate(f"() => window.scrollTo({{top: {i * vh}, left: 0, behavior: 'instant'}})")
        page.wait_for_timeout(30)
        page.screenshot(path=str(shots / f"{name}-tile{i + 1}.png"))
    page.evaluate("() => window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
    return n


def _watch_state(page, marker: str, hold_ms: int, timeout: int) -> dict[str, Any]:
    """Focus the state's first control and watch the page for `hold_ms` (B-09)."""
    try:
        el = page.locator(marker).first.element_handle(timeout=timeout)
        start = page.evaluate(JS_STATE_WATCH, el)
        page.wait_for_timeout(hold_ms)
        end = page.evaluate(JS_STATE_WATCH_END)
    except Exception as exc:  # noqa: BLE001 - a page that breaks mid-watch is reported, never fatal
        return {"error": str(exc).splitlines()[0][:160]}
    return {**start, **end, "hold_ms": hold_ms}


_GONE_JS = "(e) => !e.isConnected || !(e.offsetWidth || e.offsetHeight || e.getClientRects().length)"


def _recover(page, stt: dict[str, Any], timeout: int) -> dict[str, Any]:
    """Press the state's way out, then expect this state gone: the element that showed it hidden or detached, and no copy
    of it on the same screen (R-UX-002: an empty state has a way back; B-09). The control inside the state is pressed
    when there is one, so a working copy in a toolbar cannot stand in for a dead one in the panel (review S2)."""
    rc = stt["recover"]
    gone = rc.get("expect_hidden") or stt["marker"]
    try:
        inside = page.locator(stt["marker"]).first.locator(rc["click"])
        target, where = (inside.first, "inside the state") if inside.count() else (page.locator(rc["click"]).first,
                                                                                   "outside the state")
        before = page.locator(gone).first.element_handle(timeout=timeout)
        screen = before.evaluate("(e) => { const s = e.closest('[data-screen]'); return s ? s.getAttribute('data-screen') : null; }")
        url = page.url
        target.click(timeout=timeout)
        deadline = time.monotonic() + timeout / 1000
        while True:
            try:
                left = bool(before.evaluate(_GONE_JS))
            except Exception:  # noqa: BLE001 - its document is gone: so is the state
                left = True
            copy = left and screen and page.url == url and page.locator(f'[data-screen="{screen}"]').locator(gone).first.is_visible()
            if left and not copy:
                return {"ok": True, "click": rc["click"], "where": where}
            if time.monotonic() > deadline:
                raise TimeoutError("the state is still shown" + (" (a new copy on the same screen)" if left else ""))
            page.wait_for_timeout(100)
    except Exception as exc:  # noqa: BLE001 - a way back that does nothing is the finding
        return {"ok": False, "click": rc["click"], "error": str(exc).splitlines()[0][:160]
                + _match_report(page, {"click": rc["click"]})}


def _token_report(page, tokens: dict[str, str], max_rules: int, root: Path | None = None) -> dict[str, Any]:
    """Custom properties used where they are undefined, and design-system colours the page defines with another value.
    An error here is reported for this page, never lost with the whole suite (config batch 2 review S1)."""
    from urllib.parse import unquote, urlparse
    from ._common import canonical_colour, parse_colour
    try:
        pairs = sorted([n, v] for n, v in tokens.items())
        got = page.evaluate(JS_TOKENS, [pairs, max_rules, []])
        extra = []
        for href in got["unreadable"]:   # Chromium hides a file:// sheet's rules; read the build's own file instead
            f = Path(unquote(urlparse(href).path)) if href.startswith("file://") else None
            if f is not None and f.is_file() and (root is None or root in f.resolve().parents):
                extra.append([href, f.read_text(errors="ignore")])
        if extra:
            got = page.evaluate(JS_TOKENS, [pairs, max_rules, extra])
    except Exception as exc:  # noqa: BLE001
        return {"undefined": [], "mismatched": [], "unreadable_sheets": [], "rules_read": 0, "containers": 0, "rejected": 0,
                "not_compared": [], "error": str(exc).splitlines()[0][:200]}
    off, not_compared = [], []
    for n, d in got["defined"].items():
        mine = canonical_colour(d["resolved"]) if parse_colour(d["resolved"]) is not None else None
        want = canonical_colour(d["system"]) if parse_colour(d["system"]) is not None else None   # as the browser reads it
        if mine is None or want is None:
            not_compared.append(n)       # oklch() or another space the comparison cannot read: named, not judged
        elif mine != want:
            off.append({"name": n, "build": d["raw"], "system": tokens[n]})
    undefined = [{**u, "where": ", ".join(u["where"])} for u in got["undefined"][:20]]
    return {"undefined": undefined, "mismatched": off, "unreadable_sheets": got["unreadable"], "rules_read": got["rules"],
            "containers": got["containers"], "rejected": got["rejected"], "not_compared": not_compared}


PARITY_PROPERTIES = ("title", "controls", "search", "filter", "tables")


def parity_drifts(build: dict[str, Any], ref: dict[str, Any], t: dict[str, Any]) -> list[tuple[str, str]]:
    """What the build lost or changed against its reference on one screen at one width, as (property, what) (N-28)."""
    out = []
    bt, rt = build.get("title"), ref.get("title")
    if rt and not bt:
        out.append(("title", "no visible page title (the reference has one)"))
    elif rt and bt:
        if abs(bt["size"] - rt["size"]) > t.get("parity_title_px", 1) or bt["weight"] != rt["weight"]:
            out.append(("title", f"title {bt['size']:g} px/{bt['weight']} (reference {rt['size']:g} px/{rt['weight']})"))
        if bt["lines"] > rt["lines"]:
            out.append(("title", f"title wraps to {bt['lines']} lines (reference {rt['lines']})"))
    bc, rc = build.get("control_height"), ref.get("control_height")
    if bc is not None and rc is not None and abs(bc - rc) > t.get("parity_control_px", 4):
        out.append(("controls", f"controls {bc} px high (reference {rc} px)"))
    for what in ("search", "filter"):
        if ref.get(what) and not build.get(what):
            out.append((what, f"no {what} control (the reference has one)"))
    if ref.get("table_mode") and build.get("table_mode") and ref["table_mode"] != build["table_mode"]:
        out.append(("tables", f"tables shown as {build['table_mode']} (reference: {ref['table_mode']})"))
    return out


def _blocker(counts: dict[str, int], side: str):
    """A route handler of one argument (Playwright passes the request too when the handler takes two, which an
    `side=side` default would silently receive) that lets local loads through and counts the rest as blocked."""
    def route(r) -> None:
        if r.request.url.startswith(ALLOWED_SCHEMES):
            r.continue_()
        else:
            counts[side] += 1
            r.abort()
    return route


def _parity(browser, entry: Path, reference: dict[str, Any], screens: list[dict[str, Any]], widths: list[int],
            rep: dict[str, Any]) -> None:
    """Load each screen in the build and in the reference, at the narrowest and widest width, and keep both readings.
    Both sides load in their own contexts with non-local requests blocked alike, so a CDN stylesheet cannot make a file
    drift from itself; the requests each side made are counted and never join the build's own findings (review I1). A
    screen the reference does not render, or whose route is null, is named and skipped (I3)."""
    ref_entry, routes = Path(reference["entry"]), reference.get("routes") or {}
    ref_marks: bool | None = None
    for vw in widths:
        size = {"width": vw, "height": _height(vw)}
        ctxs, blocked = [], {"build": 0, "reference": 0}
        try:
            for side in ("build", "reference"):
                c = browser.new_context(viewport=size)
                c.route("**/*", _blocker(blocked, side))
                ctxs.append(c)
            pages = {"build": ctxs[0].new_page(), "reference": ctxs[1].new_page()}
            for scr in screens:
                row: dict[str, Any] = {"screen": scr["id"], "viewport": vw}
                if scr["id"] in routes and routes[scr["id"]] is None:
                    rep["parity"].append({**row, "skipped": "its route is null in `reference.routes`"})
                    continue
                try:
                    urls = {"build": _url(entry, scr["route"]),
                            "reference": _url(ref_entry, routes.get(scr["id"], scr["route"]))}
                    for side, page in pages.items():
                        page.goto("about:blank")
                        page.goto(urls[side])
                        _settle(page)
                        waited = page.evaluate(JS_QUIET, [300, 3000])   # both read settled, whatever each one's load takes
                        row[side] = page.evaluate(JS_PARITY)
                        if waited >= 3000:
                            row.setdefault("restless", []).append(side)
                    if ref_marks is None:
                        ref_marks = bool(pages["reference"].evaluate("() => !!document.querySelector('[data-screen]')"))
                    if ref_marks and not pages["reference"].evaluate(
                            "(id) => !!document.querySelector(`[data-screen='${id}']`)", scr["id"]):
                        row = {"screen": scr["id"], "viewport": vw,
                               "skipped": "the reference does not render this screen (name its route in `reference.routes`, "
                                          "or set it to null)"}
                except Exception as exc:  # noqa: BLE001 - one screen that cannot be compared is reported, not fatal
                    row["error"] = str(exc).splitlines()[0][:160]
                rep["parity"].append(row)
        except Exception as exc:  # noqa: BLE001 - parity is advisory: it never takes the rest of the suite down (S4)
            rep["parity"].append({"screen": "*", "viewport": vw, "error": str(exc).splitlines()[0][:160]})
        finally:
            for c in ctxs:
                try:   # a blocked request still pending when the context closes must not raise out of here
                    c.unroute_all(behavior="ignoreErrors")
                    c.close()
                except Exception:  # noqa: BLE001
                    pass
        rep.setdefault("parity_blocked", {}).update({f"{k}@{vw}": v for k, v in blocked.items() if v})


def _spread(items: list, n: int) -> list:
    """`n` of `items`, evenly spread, the first and the last included."""
    if n <= 0:
        return []
    if len(items) <= n:
        return list(items)
    if n == 1:
        return [items[0]]
    return list(dict.fromkeys(items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)))


def _record_tail(tail: str) -> bool:
    """The last segment of a record route: one id, no deeper path, query or fragment (`R-7`, not `R-7/notes`, `?sort=`)."""
    return bool(tail) and not any(c in tail for c in "/?#")


def suite_screens(design_screens: list[dict[str, Any]], samples: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """The screens the suite sweeps, with what the width samples need: each screen's kind and the plan's samples. N13's
    check and `pdg check-prototype` build them here, so both sample the same records (W53 review I1)."""
    return [{"id": s["id"], "route": s.get("route"), "kind": s.get("kind"), "samples": list((samples or {}).get(s["id"], []))}
            for s in design_screens]


def sample_routes(screens: list[dict[str, Any]], links: set[str], cap: int = 24,
                  cut: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """More records of each record screen for the width checks: one record proves the template for one record, not the
    screen (W53: a third head action overflowed 17 of 31 records at 320 px, never the one sampled). The plan's `samples`
    come first (worst cases); then records the app links to one level under the same parent (`#/signal/<id>` beside
    `#/signal/SCI-005`), spread evenly. Never a design screen's own route: its overflow is its own. At most `cap` routes
    in all, shared by the screens that have any; plan samples over a screen's share go to `cut`, to be named. Whether
    each renders its screen is checked before it is read."""
    design = {s["route"] for s in screens if s.get("route")}
    wanted: dict[str, tuple[list[str], list[str]]] = {}
    for s in screens:
        named = [r for r in dict.fromkeys(s.get("samples") or []) if r and r not in design]
        route = s.get("route") or ""
        parent = route.rsplit("/", 1)[0] + "/" if s.get("kind") == "record" and route.count("/") >= 2 else None
        found = sorted(r for r in links if parent and r.startswith(parent) and r not in design and r not in named
                       and _record_tail(r[len(parent):]))
        if named or found:
            wanted[s["id"]] = (named, found)
    if not wanted or cap <= 0:
        return {}
    share = max(1, cap // len(wanted))
    out = {}
    for sid, (named, found) in list(wanted.items())[:cap]:
        take = named[:share]
        if cut is not None and named[share:]:
            cut[sid] = named[share:]
        out[sid] = take + _spread(found, share - len(take))
    return {k: v for k, v in out.items() if v}


def _short(route: str, n: int = 80) -> str:
    """An app's href, cut for a finding's text (W53 review S7)."""
    return route if len(route) <= n else route[:n - 1] + "…"


def _thin(widths: list[int], planned: list[int]) -> list[int]:
    """The widths a sampled record is read at: up to 5 below the narrowest planned width (where a record's content most
    often breaks), the band width at or below each planned width, 4 across the band, and the widest (W53 review S2)."""
    if not widths:
        return []
    lo = min(planned) if planned else widths[0]
    near = {max((w for w in widths if w <= v), default=widths[0]) for v in planned}
    return sorted(set(_spread([w for w in widths if w <= lo], 5)) | near | set(_spread(widths, 4)) | {widths[-1]})


def band_widths(viewports: list[int], step: int, cap: int = 80) -> list[int]:
    """Every `step` px from the narrowest to the widest planned width, both ends included (W47); thinned evenly to `cap`
    widths. A 110 % zoom of a planned width lays out like that width / 1.1, inside the band for every planned width
    but the narrowest."""
    if not viewports or step <= 0:
        return []
    lo, hi = min(viewports), max(viewports)
    widths = sorted(set(range(lo, hi, step)) | {hi})
    return widths if len(widths) <= cap else [widths[round(i * (len(widths) - 1) / (cap - 1))] for i in range(cap)]


def _band_read(page, quiet_ms: int, cap_ms: int) -> dict[str, Any]:
    waited = page.evaluate(JS_QUIET, [quiet_ms, cap_ms])
    return {**page.evaluate(JS_BAND), **({"restless": True} if waited >= cap_ms else {})}


def _page_overflow(page) -> dict[str, Any]:
    """How far the page runs past the window, and the region around the view that scrolls it when that is not the
    document (R2-27)."""
    o = page.evaluate(JS_OVERFLOW)
    return {"overflow_px": o["px"], **({"overflow_in": o["by"]} if o["by"] else {})}


def _inside(where: set[str] | str | None) -> str:
    """The region a page overflow happens in, for a finding's text, when that is not the document (R2-27)."""
    names = sorted(where) if isinstance(where, set) else [where] if where else []
    return f" (inside {', '.join(names[:2])}, which scrolls sideways around the screen)" if names else ""



def _spacing_breaks(plain: dict[str, Any], spaced: dict[str, Any]) -> dict[str, Any]:
    """What 1.4.12 spacing breaks that was not broken without it: text past its box, a cut select value, page overflow,
    a word broken mid-word (field run W56)."""
    def new(kind: str, key) -> list:
        had = {key(x) for x in plain.get(kind, [])}
        return [x for x in spaced.get(kind, []) if key(x) not in had]
    return {"text_spacing_spill": new("spill", lambda x: (x["el"], x.get("text"))),
            "text_spacing_cut": new("cut", lambda x: (x["el"], x.get("text"))),
            "text_spacing_midword": new("midword", lambda x: (x["word"], x["el"])),
            "text_spacing_overflow": spaced["overflow"] if spaced["overflow"] > 1 and plain["overflow"] <= 1 else 0}


def _flagged(r: dict[str, Any]) -> bool:
    return r.get("overflow", 0) > 1 or bool(r.get("midword")) or bool(r.get("spill")) or bool(r.get("cut"))


def _await_screen(page, sid: str, timeout_ms: int) -> None:
    """Wait, briefly, until the route shows its screen: an app that renders after load is measured rendered, not blank.
    Only for a screen known to render (the sweep saw it, or a sample was verified), so a page without markers waits
    for nothing."""
    try:
        page.wait_for_function(JS_SHOWS_SCREEN, arg=sid, timeout=timeout_ms)
    except Exception:  # noqa: BLE001 - measured as it is; FUNC-STATES names a route that does not render its screen
        pass


def _chosen(browser, entry: Path, screens: list[dict[str, Any]], widths: list[int], rep: dict[str, Any],
            renders: set[str], wait_ms: int, budget_s: float = 90.0, per_screen: int = 6, confirm_cap: int = 20) -> None:
    """Each screen with its selects' longest values chosen, read at the phone widths: every sweep loads a screen with its
    filters at their defaults, the shortest values, so a panel a long chosen value widens past the screen passed every
    check until a reviewer chose one (field run W58). One select at a time, chosen as a user would (so the app reacts),
    read from the widest of `widths` down, then once more under 1.4.12 spacing at the narrowest. A select is chosen on the
    first screen it is on (by its id, or by its label and longest value).

    A select a disclosure hides (a phone's "Filters" button, a closed <details>) is reached by opening it first, as a user
    would: D-214's long study type sat in exactly such a panel. Every state is read the same way, the screen as loaded
    (`default`), with its disclosures open (`opened`) and with a value chosen (`chosen`), so each is compared with the
    state before it at the same width and under the same spacing (W58 replay: compared with the band, which has no 320 px
    reading, every cut at 320 px read as the choice's). An overflow is confirmed on a fresh load, with the state before it
    read fresh at the same width too (review S2).

    Each load starts as a first visit, with empty storage, so a value the app saved is not the next load's default; a
    disclosure that cannot be clicked, or that leaves the screen, is named and left closed; a choice that leaves the
    screen is named, never read as the screen's (review I1–I3)."""
    rep.update(chosen=[], chosen_widths=sorted(set(widths)), chosen_hidden={}, chosen_toggles={}, chosen_capped={},
               chosen_per_screen=per_screen)
    if not widths:
        return
    widths, top = sorted(set(widths)), max(widths)
    deadline, done, unread, skipped = time.monotonic() + budget_s, set(), 0, 0
    ctx = None
    try:
        ctx = browser.new_context(viewport={"width": top, "height": _height(top)})
        ctx.add_init_script("try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}")
        ctx.route("**/*", _blocker({"chosen": 0}, "chosen"))
        page = ctx.new_page()

        def load(route, sid: str, w: int) -> None:
            page.set_viewport_size({"width": w, "height": _height(w)})
            page.goto("about:blank")
            page.goto(_url(entry, route))
            _settle(page)
            if sid in renders:
                _await_screen(page, sid, wait_ms)

        def left(sid: str, doc: float) -> bool:
            """The screen being read is gone: its marker no longer shows, or, for a screen found without one, the page is a
            new document (a filter written into the URL is not leaving; review nit)."""
            return (not page.evaluate(JS_SHOWS_SCREEN, sid) if sid in renders
                    else page.evaluate("() => performance.timeOrigin") != doc)

        def open_at(route, sid: str, w: int, reveal: bool = True) -> list[str]:
            load(route, sid, w)
            bad, opened = rep["chosen_toggles"].setdefault(sid, {}), []
            for _ in range(8 if reveal else 0):   # each disclosure that holds a select, once
                h = page.evaluate_handle(JS_SELECT_TOGGLE, opened + list(bad)).as_element()
                if h is None or len(opened) >= 4:
                    break
                name, doc = h.evaluate(JS_TOGGLE_NAME), page.evaluate("() => performance.timeOrigin")
                hidden = page.evaluate(JS_SELECTS)["hidden"]
                try:
                    h.click(timeout=wait_ms)
                    page.evaluate(JS_QUIET, [150, 1000])
                    why = ("leaves the screen" if left(sid, doc)   # a link or a submit button: another screen
                           else "revealed no select" if page.evaluate(JS_SELECTS)["hidden"] >= hidden else "")
                except Exception:  # noqa: BLE001 - covered, detached, or its page went away: the rest is still read
                    why = "could not be clicked"
                if why:   # start the screen again without it, so what the click changed is not read (review S-b)
                    bad[name] = why
                    load(route, sid, w)
                    opened = []
                    continue
                opened.append(name)
            if not bad:
                del rep["chosen_toggles"][sid]
            return opened

        def choose(el: str, text: str, sid: str) -> str:
            """'' once chosen, else why not."""
            x = next((x for x in page.evaluate(JS_SELECTS)["picks"] if x["el"] == el and x["text"] == text), None)
            if x is None:
                return "its longest value could not be chosen on this load"
            doc = page.evaluate("() => performance.timeOrigin")
            # the element JS_SELECTS counted, not Playwright's nth select: its CSS engine also counts selects in open shadow
            # roots, which querySelectorAll does not
            h = page.evaluate_handle("(i) => document.querySelectorAll('select')[i]", x["index"]).as_element()
            h.select_option(index=x["longest"], timeout=wait_ms)
            page.evaluate(JS_QUIET, [150, 1000])
            return "choosing it leaves the screen" if left(sid, doc) else ""

        def read(row: dict[str, Any]) -> None:
            """The page as it is, at each width from the widest down, then under 1.4.12 spacing at the narrowest."""
            last = None
            for w in reversed(widths):
                page.set_viewport_size({"width": w, "height": _height(w)})
                last = _band_read(page, 150, 1000)
                rep["chosen"].append({**row, "width": w, **last})
            page.add_style_tag(content=TEXT_SPACING_STYLE)
            page.wait_for_timeout(20)
            rep["chosen"].append({**row, "width": widths[0], "spacing": True, **_spacing_breaks(last, page.evaluate(JS_BAND))})
        for scr in screens:
            base = {"screen": scr["id"], "route": scr["route"], "select": None, "value": None}
            if time.monotonic() > deadline:   # before the load: a spent budget costs nothing more (review S4)
                skipped += 1
                continue
            try:
                opened = open_at(scr["route"], scr["id"], top)
                if rep["chosen_toggles"].get(scr["id"]):   # the ones that failed are skipped from the start now, so the
                    opened = open_at(scr["route"], scr["id"], top)   # screen opens as every later load will (review S1)
                seen = page.evaluate(JS_SELECTS)
                fresh_picks = [x for x in seen["picks"] if (x["id"] or f"{x['el']}={x['text']}") not in done]
                picks = fresh_picks[:per_screen]
                if len(fresh_picks) > per_screen:
                    rep["chosen_capped"][scr["id"]] = len(fresh_picks)
                if seen["hidden"]:
                    rep["chosen_hidden"][scr["id"]] = seen["hidden"]
                if not picks and not opened:
                    continue
                if opened:
                    read({**base, "state": "opened", "opened": opened})
                    open_at(scr["route"], scr["id"], top, reveal=False)
                read({**base, "state": "default"})   # without a disclosure, the page loaded above is the default
                if opened:
                    base["opened"] = opened
            except Exception as exc:  # noqa: BLE001 - a screen that cannot be read is named, not fatal
                rep["chosen"].append({**base, "width": None, "error": str(exc).splitlines()[0][:160]})
                continue
            for x in picks:
                if time.monotonic() > deadline:
                    unread += 1
                    continue
                done.add(x["id"] or f"{x['el']}={x['text']}")
                row = {**base, "state": "chosen", "select": x["el"], "value": x["text"]}
                try:
                    why = ("its disclosures opened differently on this load"
                           if open_at(scr["route"], scr["id"], top) != base.get("opened", []) else "")
                    why = why or choose(x["el"], x["text"], scr["id"])
                    if why:
                        rep["chosen"].append({**row, "width": None, "error": why})
                        continue
                    read(row)
                except Exception as exc:  # noqa: BLE001
                    rep["chosen"].append({**row, "width": None, "error": str(exc).splitlines()[0][:160]})
        # one width of every flagged state first, the narrowest, then the next: a cap of rows spent on one state's five
        # widths left the next states unconfirmed (review R2). A row never tried still counts, as in the band
        flagged = [r for r in rep["chosen"] if r.get("width") and not r.get("spacing") and r.get("state") != "default"
                   and r.get("overflow", 0) > 1]
        rank: dict[tuple[Any, ...], int] = {}
        for r in sorted(flagged, key=lambda r: r["width"]):
            k = (r["screen"], r["state"], r["select"], r["value"])
            r["_rank"] = rank[k] = rank.get(k, -1) + 1
        for r in sorted(flagged, key=lambda r: (r.pop("_rank"), r["width"]))[:confirm_cap]:
            if time.monotonic() > deadline + 30:   # a short grace after the budget: the rest stay as read
                break
            try:
                got = open_at(r["route"], r["screen"], r["width"], reveal=bool(r.get("opened")))
                why = ("its disclosures opened differently on this load" if got != (r.get("opened") or [])
                       else "" if r["state"] == "opened" else choose(r["select"], r["value"], r["screen"]))
                if why:
                    r["confirm_error"] = why
                    continue
                fresh = _band_read(page, 300, 2000)
                base_overflow = 0
                if fresh["overflow"] > 1:   # the state before it, read fresh at the same width too (review S2)
                    open_at(r["route"], r["screen"], r["width"], reveal=r["state"] == "chosen" and bool(r.get("opened")))
                    base_overflow = _band_read(page, 300, 2000)["overflow"]
                r.update(resize_overflow=r["overflow"], overflow=fresh["overflow"], overflow_in=fresh.get("overflow_in", ""),
                         base_overflow=base_overflow, confirmed=True)
            except Exception as exc:  # noqa: BLE001 - an unconfirmed reading is reported as such
                r["confirm_error"] = str(exc).splitlines()[0][:160]
    except Exception as exc:  # noqa: BLE001 - this pass never takes the rest of the suite down
        rep["chosen"].append({"screen": "*", "width": None, "error": str(exc).splitlines()[0][:160]})
    finally:
        rep["chosen_unread"], rep["chosen_unread_screens"] = unread, skipped
        if ctx is not None:
            try:
                ctx.unroute_all(behavior="ignoreErrors")
                ctx.close()
            except Exception:  # noqa: BLE001
                pass


def _state_fills(browser, entry: Path, screens: list[dict[str, Any]], width: int, rep: dict[str, Any], renders: set[str],
                 wait_ms: int, status: dict[str, str], budget_s: float = 60.0, click_budget_s: float = 60.0) -> None:
    """Each list's interactive states against its status colours, at the widest planned width (R2-26): the fill of the
    item marked current (or selected, or pressed), of a resting item and of that item hovered by the pointer, and the
    marks inside them (a score box, a pill). Read after every transition has finished. Then, on its own budget, a click
    on a resting item of up to 3 lists per screen, each on a fresh load (R2-29): a link, an item in a `nav`, or a list a
    click took to another screen before (the shell's rail) is not clicked (part 2 review S3)."""
    rep["state_fills"], rep["state_fills_unread"] = [], 0
    deadline, ctx = time.monotonic() + budget_s, None
    try:
        ctx = browser.new_context(viewport={"width": width, "height": _height(width)})
        ctx.add_init_script("try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}")   # each load a first visit
        ctx.route("**/*", _blocker({"state_fills": 0}, "state_fills"))
        page = ctx.new_page()

        def load(scr: dict[str, Any]) -> None:
            page.goto("about:blank")
            page.goto(_url(entry, scr["route"]))
            _settle(page)
            if scr["id"] in renders:
                _await_screen(page, scr["id"], wait_ms)
            page.mouse.move(-1, -1)   # off the page: (0, 0) is on a rail's first item (review I3)
            page.evaluate(JS_SETTLED)
        read: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for scr in screens:
            if time.monotonic() > deadline:
                rep["state_fills_unread"] += 1
                continue
            try:
                load(scr)
                got = page.evaluate(JS_STATE_GROUPS, status)
                for i, g in enumerate(got["groups"]):
                    if time.monotonic() > deadline:
                        g["hover_error"] = "the time budget ran out"
                        continue
                    try:   # one item that cannot be hovered (pointer-events: none) loses only its own group (review I3)
                        item = page.evaluate_handle("(i) => window.__pdgRest[i]", i).as_element()
                        item.hover(timeout=wait_ms, position=_near_edge(item))   # not on a pill that has its own hover
                        page.evaluate(JS_SETTLED)
                        seen = page.evaluate(JS_ITEM, i)
                        if seen.get("redrawn"):
                            g["hover_error"] = "redrawn while hovered"
                        else:
                            g["hover"] = seen
                    except Exception as exc:  # noqa: BLE001
                        g["hover_error"] = str(exc).splitlines()[0][:160]
                    page.mouse.move(-1, -1)
                    page.evaluate(JS_SETTLED)
                row = {"screen": scr["id"], "groups": got["groups"], "status": got["status"]}
                rep["state_fills"].append(row)
                read.append((scr, row))
            except Exception as exc:  # noqa: BLE001 - a screen that cannot be read is named, not fatal
                rep["state_fills"].append({"screen": scr["id"], "error": str(exc).splitlines()[0][:160]})
        click_deadline, gone = time.monotonic() + click_budget_s, set()
        for scr, row in read:   # the clicks, after every hover reading, so a slow app starves neither (review S3)
            clicks = 0
            try:
                for i, g in enumerate(row["groups"]):   # a click on a resting item, on a fresh load each (R2-29)
                    # the shell's rail took a click elsewhere once: the same list, the same items, on every screen; a list
                    # that only shares its label is not it (part 2 review N-b)
                    name = f"{g['list']} > {g['el']} | {g.get('rest_text', '')}"
                    if clicks >= 3 or g.get("rest_link") or name in gone:
                        continue
                    if g.get("rest_disabled"):
                        g["click"] = {"skipped": "every other item in the list is disabled"}
                        continue
                    if time.monotonic() > click_deadline:
                        g["click"] = {"skipped": "the time budget ran out"}
                        continue
                    load(scr)
                    again = page.evaluate(JS_STATE_GROUPS, status)["groups"]
                    if i >= len(again) or again[i]["el"] != g["el"]:
                        continue
                    clicks += 1
                    try:
                        item = page.evaluate_handle("(i) => window.__pdgRest[i]", i).as_element()
                        item.scroll_into_view_if_needed(timeout=wait_ms)   # its box as clicked (review S-A)
                        page.evaluate(JS_CLICK_MARK, i)
                        item.click(timeout=wait_ms, position=_near_edge(item))
                        page.evaluate(JS_CLICK_SETTLED, 1000)
                        page.evaluate(JS_QUIET, [150, 1000])
                        page.evaluate(JS_SETTLED)
                        left = page.evaluate("() => !window.__pdgClicked") or (
                            scr["id"] in renders and not page.evaluate(JS_SHOWS_SCREEN, scr["id"]))
                        if left:   # another screen: nothing here to judge, and the same list elsewhere is the shell's
                            gone.add(name)
                        g["click"] = {"left": True} if left else page.evaluate(JS_CLICKED)
                    except Exception as exc:  # noqa: BLE001 - an item that cannot be clicked is named
                        g["click"] = {"error": str(exc).splitlines()[0][:160]}
            except Exception as exc:  # noqa: BLE001 - the screen's clicks are lost, its hover readings kept
                row["click_error"] = str(exc).splitlines()[0][:160]
    except Exception as exc:  # noqa: BLE001 - this pass never takes the rest of the suite down
        rep["state_fills"].append({"screen": "*", "error": str(exc).splitlines()[0][:160]})
    finally:
        if ctx is not None:
            try:
                ctx.unroute_all(behavior="ignoreErrors")
                ctx.close()
            except Exception:  # noqa: BLE001
                pass


def _focus_drawn(page, pad: int = 8) -> bool:
    """Whether focus changes what is on screen in or around the focused control, which has no outline or shadow of its
    own: a marker a chart point reveals inside it, a wrapper's :focus-within ring round it (refresh field run). Its box
    and a margin are read focused, with the previous stop focused, then as before the Tab (blurred, and each attribute
    the move changed set back: a class a script adds on focus and keeps after blur), animations finished; then the page
    and focus are put back."""
    try:
        box = page.evaluate(JS_FOCUS_BOX, pad)
        if not box:
            return False
        focused = page.screenshot(clip=box, animations="disabled")
        page.evaluate(JS_BEFORE_FOCUS)
        blurred = page.screenshot(clip=box, animations="disabled")
        page.evaluate(JS_PREV_FOCUS)
        previous = page.screenshot(clip=box, animations="disabled")
        return focused != previous and focused != blurred
    except Exception:  # noqa: BLE001 - unread is not drawn: the finding stands, as before this reading
        return False
    finally:
        try:
            page.evaluate(JS_AFTER_FOCUS)
        except Exception:  # noqa: BLE001
            pass


def _near_edge(item) -> dict[str, float] | None:
    """A point inside an item near its left edge, clear of what it holds: in from the edge by its corner's radius, so a
    fully rounded chip is pressed inside its round end and a square row at 2 px, beside rather than on a pill it holds
    (config batch 5 review I7, S13). None: the item has no box, and Playwright picks its centre."""
    bb = item.bounding_box()
    if not bb or bb["width"] < 1 or bb["height"] < 1:
        return None
    radius = float(item.evaluate("(e) => parseFloat(getComputedStyle(e).borderTopLeftRadius) || 0"))
    return {"x": min(max(2.0, min(radius, bb["height"] / 2)), bb["width"] / 2), "y": bb["height"] / 2}


def _rgba(css: str | None) -> tuple[float, float, float, float] | None:
    """rgb()/rgba() as Chromium computes it, or None for no fill."""
    m = re.match(r"rgba?\(([^)]*)\)", css or "")
    if not m:
        return None
    v = [float(x) for x in re.split(r"[,\s/]+", m.group(1).strip()) if x]
    rgba = (*v[:3], v[3] if len(v) > 3 else 1.0)
    return None if rgba[3] == 0 else rgba   # type: ignore[return-value]


def _near(a: str | None, b: str | None) -> bool:
    """One colour: the same alpha, and each channel within 3 of 255 (a transition's last frame, a rounding)."""
    x, y = _rgba(a), _rgba(b)
    return bool(x and y) and abs(x[3] - y[3]) < 0.05 and max(abs(p - q) for p, q in zip(x[:3], y[:3])) <= 3


def _twin(m: dict[str, Any], marks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The mark in the same place in another item of the list: by its place from the first child, or, when the other item
    holds an extra element in front (the "where you are" bar), from the last; either way of the same tag and sharing a
    class (review S9)."""
    def like(x: dict[str, Any]) -> bool:
        return x["key"].split("@")[0] == m["key"].split("@")[0] and (bool(set(x["cls"]) & set(m["cls"])) or not x["cls"] and not m["cls"])
    return (next((x for x in marks if x["key"] == m["key"] and like(x)), None)
            or next((x for x in marks if x["alt"] == m["alt"] and like(x)), None)
            # the same place from both ends is the same slot, whatever its class ("act" there, "white" here; review S12)
            or next((x for x in marks if x["key"] == m["key"] and x["alt"] == m["alt"]), None))


def _grey(css: str) -> bool:
    """White, grey or black: no hue a status could carry."""
    x = _rgba(css)
    return bool(x) and max(x[:3]) - min(x[:3]) <= 10


def _on(css: str, surface: str) -> str:
    """A fill composited over its surface, as the eye sees it."""
    f, s = _rgba(css), _rgba(surface) or (255.0, 255.0, 255.0, 1.0)
    if f is None:
        return surface
    return "rgb(" + ", ".join(str(round(f[3] * p + (1 - f[3]) * q)) for p, q in zip(f[:3], s[:3])) + ")"


def _ratio(a: str, b: str) -> float:
    la, lb = (luminance(tuple(c / 255 for c in (_rgba(x) or (255.0, 255.0, 255.0, 1.0))[:3])) for x in (a, b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _rendering_samples(browser, entry: Path, samples: dict[str, list[str]], width: int, timeout_ms: int,
                       design_shows: dict[str, set[str]] | None = None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(kept, dropped). A sample counts as a record of its screen only when it renders that screen, and the same
    screens its design route shows (a list beside a record pane is not a record): a missing record ("not found"), a
    route that needs state the app holds in memory, or another page is dropped and named, never measured as the screen,
    whose defect a fix to the screen could then never close (W53 review C1)."""
    keep: dict[str, list[str]] = {}
    dropped: dict[str, list[str]] = {}
    if not samples:
        return keep, dropped
    ctx = browser.new_context(viewport={"width": width, "height": _height(width)})
    try:
        ctx.route("**/*", _blocker({"samples": 0}, "samples"))
        page = ctx.new_page()
        for sid, routes in samples.items():
            for route in routes:
                try:
                    page.goto("about:blank")
                    page.goto(_url(entry, route), timeout=3 * timeout_ms)
                    page.wait_for_function(JS_SHOWS_SCREEN, arg=sid, timeout=timeout_ms)
                    want = (design_shows or {}).get(sid)
                    _settle(page)                         # read once settled, as the design route was
                    if want and set(page.evaluate(JS_SHOWN_SCREENS)["shown"]) != want:
                        raise ValueError("shows other screens than its design route")
                    keep.setdefault(sid, []).append(route)
                except Exception:  # noqa: BLE001 - it does not show its screen alone: not a record of it
                    dropped.setdefault(sid, []).append(route)
                    try:
                        page.close()
                    except Exception:  # noqa: BLE001 - a crashed renderer: the context closes it
                        pass
                    page = ctx.new_page()
    finally:
        try:
            ctx.unroute_all(behavior="ignoreErrors")
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
    return keep, dropped


def _band(browser, entry: Path, screens: list[dict[str, Any]], widths: list[int], rep: dict[str, Any],
          confirm_cap: int = 60, samples: dict[str, list[str]] | None = None, planned: list[int] | None = None,
          budget_s: float = 90.0, renders: set[str] | None = None, wait_ms: int = 2000) -> None:
    """Each screen once, resized through the band from the widest width down, read once its DOM is quiet (W47). A width
    that shows a problem is read again on a fresh load at that width, which is how a user arrives there: a chart sized
    once at load, or a resize handler still waiting, must not fail the page (review I1). Only what the fresh load also
    shows counts."""
    if not widths:
        return
    ctx = None
    try:
        ctx = browser.new_context(viewport={"width": widths[-1], "height": _height(widths[-1])})
        ctx.route("**/*", _blocker({"band": 0}, "band"))
        page = ctx.new_page()
        for scr in screens:
            try:
                page.set_viewport_size({"width": widths[-1], "height": _height(widths[-1])})
                page.goto("about:blank")
                page.goto(_url(entry, scr["route"]))
                _settle(page)
                if scr["id"] in (renders or set()):
                    _await_screen(page, scr["id"], wait_ms)
                for w in reversed(widths):
                    page.set_viewport_size({"width": w, "height": _height(w)})
                    rep["band"].append({"screen": scr["id"], "route": scr["route"], "width": w, **_band_read(page, 150, 1000)})
            except Exception as exc:  # noqa: BLE001 - one screen that cannot be swept is reported, not fatal
                rep["band"].append({"screen": scr["id"], "width": None, "error": str(exc).splitlines()[0][:160]})
        # more records of a record screen, on a thinned band (W53), within a time budget
        thin = _thin(widths, planned or [widths[0]])
        deadline, unread = time.monotonic() + budget_s, 0
        if samples:
            rep["band_samples"] = {"routes": sum(len(v) for v in samples.values()), "widths": thin, "unread": 0}
        for sid, extra in (samples or {}).items():
            for route in extra:
                if time.monotonic() > deadline:
                    unread += 1
                    rep["band_samples"]["unread"] = unread
                    continue
                try:
                    page.set_viewport_size({"width": thin[-1], "height": _height(thin[-1])})
                    page.goto("about:blank")
                    page.goto(_url(entry, route))
                    _settle(page)
                    _await_screen(page, sid, wait_ms)             # a kept sample renders its screen
                    for w in reversed(thin):
                        page.set_viewport_size({"width": w, "height": _height(w)})
                        rep["band"].append({"screen": sid, "route": route, "sample": True, "width": w,
                                            **_band_read(page, 150, 1000)})
                except Exception as exc:  # noqa: BLE001 - a sample that cannot be swept is reported, not fatal
                    rep["band"].append({"screen": sid, "route": route, "sample": True, "width": None,
                                        "error": str(exc).splitlines()[0][:160]})
        routes = {s["id"]: s["route"] for s in screens}
        # what a resize can fake (overflow, a mid-word break, spill) is confirmed first; a cut select, read on its own box,
        # gets what budget is left, one reading per select, so it cannot crowd out another screen's readings (review C1)
        flagged = [r for r in rep["band"] if r.get("width") and _flagged(r)]
        layout = [r for r in flagged if r.get("overflow", 0) > 1 or r.get("midword") or r.get("spill")]
        taken, cut_only = {id(r) for r in layout}, []
        for r in flagged:
            key = (r["screen"], r.get("route"), tuple(sorted(x["el"] for x in r.get("cut", []))))
            if id(r) not in taken and key not in {k for k, _ in cut_only}:
                cut_only.append((key, r))
        for r in (layout + [r for _, r in cut_only])[:confirm_cap]:
            try:
                page.set_viewport_size({"width": r["width"], "height": _height(r["width"])})
                page.goto("about:blank")
                page.goto(_url(entry, r.get("route") or routes[r["screen"]]))
                _settle(page)
                if r.get("sample") or r["screen"] in (renders or set()):
                    _await_screen(page, r["screen"], wait_ms)
                fresh = _band_read(page, 300, 2000)
                r["resize_only"] = {k: r.get(k) for k in ("overflow", "midword", "spill", "cut")}
                r.update(overflow=fresh["overflow"], midword=fresh["midword"], spill=fresh["spill"], cut=fresh.get("cut", []),
                         overflow_in=fresh.get("overflow_in", ""), confirmed=True)
            except Exception as exc:  # noqa: BLE001 - an unconfirmed reading is reported as such
                r["confirm_error"] = str(exc).splitlines()[0][:160]
    except Exception as exc:  # noqa: BLE001 - the band never takes the rest of the suite down (review S7)
        rep["band"].append({"screen": "*", "width": None, "error": str(exc).splitlines()[0][:160]})
    finally:
        if ctx is not None:
            try:
                ctx.unroute_all(behavior="ignoreErrors")
                ctx.close()
            except Exception:  # noqa: BLE001
                pass


def _ranges(widths: list[int], swept: list[int]) -> str:
    """Flagged widths as ranges of consecutive sampled widths: 1204, 1224, 1244 → "1204–1244 px" (review S5)."""
    pos = {w: i for i, w in enumerate(sorted(swept))}
    out, run = [], []
    for w in sorted(widths):
        if run and pos.get(w, -9) - pos.get(run[-1], -9) != 1:
            out.append(run)
            run = []
        run.append(w)
    if run:
        out.append(run)
    return ", ".join(f"{r[0]}–{r[-1]} px" if len(r) > 1 else f"{r[0]} px" for r in out)


def _beat(msg: str) -> None:
    """One unbuffered progress line per unit of work, so a suite that runs for minutes shows where it is (field run 2,
    R2-05). On stderr: stdout stays the verdict."""
    print(f"pdg browser: {msg}", file=sys.stderr, flush=True)


def run_suite(entry: Path, scenarios: list[dict[str, Any]], states: list[dict[str, Any]], screens: list[dict[str, Any]],
              viewports: list[int], t: dict[str, Any], out: Path, forbidden: list[str] | None = None,
              tokens: dict[str, str] | None = None, reference: dict[str, Any] | None = None,
              status: dict[str, str] | None = None, documented: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Run the whole browser suite. Returns the report (also written to out/browser-report.json). `status`: the design
    system's status colours (name → #rrggbb), which no interactive state may take (R2-26), except on the components
    `documented` names for that colour (name → CSS classes: the design system's own state fills)."""
    from playwright.sync_api import sync_playwright

    shots = out / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    tags, timeout = t["axe_tags"], int(t["step_timeout_ms"])
    rep: dict[str, Any] = {"entry": str(entry), "viewports": viewports, "scenarios": [], "states": [], "screens": [],
                           "state_documented": {k: list(v) for k, v in (documented or {}).items()},
                           "axe": [], "reflow_320": [], "reduced_motion": [], "console": [], "requests": [], "timing_ms": [],
                           "forbidden_text": [], "forbidden_checked": list(forbidden or []), "tokens": [], "parity": [],
                           "reference": (reference or {}).get("entry"), "band": [], "band_step": int(t.get("band_step_px", 20)), "samples": {}, "reference_expected": (reference or {}).get("expected", []),
                           # headless Chromium's default: showing them would change every overflow and reflow measurement
                           "scrollbars": "hidden (headless Chromium's --hide-scrollbars default): no screenshot shows a "
                                         "scroll cue, and a scroller's offsetHeight - clientHeight reads 0"}
    col = Collector()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            widest = max(viewports) if viewports else 0
            links: set[str] = set()                                   # in-app record links, for the width samples (W53)
            for vw in viewports:
                size = {"width": vw, "height": _height(vw)}
                for s in scenarios:
                    _beat(f"{vw} px · scenario {s['id']}")
                    ctxb = browser.new_context(viewport=size)
                    page = ctxb.new_page()
                    col.attach(page, f"{s['id']}@{vw}")
                    # a scenario that starts with a goto opens that URL cold, as a shared link does; a hash change on the
                    # entry never runs the app's start-up routing (field run 2, R2-06)
                    first = s["steps"][0] if s["steps"] else {}
                    cold = first.get("goto") if isinstance(first, dict) else None
                    page.goto(_url(entry, cold))
                    _settle(page)
                    rec = {"id": s["id"], "viewport": vw, "passed": True, "failed_step": None, "error": ""}
                    hits: list[dict[str, Any]] = []
                    for i, step in enumerate(s["steps"]):
                        step = {k: v for k, v in step.items() if v is not None}
                        if i == 0 and cold is not None:
                            continue
                        try:
                            _run_step(page, step, entry, timeout, shots, f"{s['id']}-{vw}", tags, hits)
                        except Exception as exc:  # noqa: BLE001 - a failed step is the finding
                            rec.update(passed=False, failed_step=i + 1, error=f"step {i + 1} {json.dumps(step)[:120]}: "
                                                                               f"{str(exc).splitlines()[0][:200]}"
                                                                               f"{_match_report(page, step)}")
                            page.screenshot(path=str(shots / f"{s['id']}-{vw}-FAILED.png"), full_page=True)
                            break
                    rep["scenarios"].append(rec)
                    for h in hits:
                        rep["axe"].append({**h, "screen": s["id"], "viewport": vw})
                    ctxb.close()
                _beat(f"{vw} px · sweep of {len(screens)} screens and {len(states)} states")
                ctxb = browser.new_context(viewport=size)
                page = ctxb.new_page()
                col.attach(page, f"sweep@{vw}")
                for scr in screens:
                    page.goto("about:blank")                      # each route loads cold, like a shared link (R2-06)
                    page.goto(_url(entry, scr["route"]))
                    _settle(page)
                    rep["timing_ms"].append({"screen": scr["id"], "viewport": vw, "dcl": page.evaluate(JS_TIMING)})
                    # the route must render its own screen in a fresh session, or every check below measures another page
                    try:
                        page.wait_for_function(JS_SHOWS_SCREEN, arg=scr["id"], timeout=timeout)
                        renders = True
                    except Exception:  # noqa: BLE001 - the route shows something else: that is the finding
                        renders = False
                    _forbidden(page, forbidden, scr["id"], vw, rep)
                    if vw == viewports[0]:
                        links.update(page.evaluate(JS_HASH_LINKS))
                    row = {"screen": scr["id"], "route": scr["route"], "viewport": vw, "renders_screen": renders,
                           "shows": sorted(page.evaluate(JS_SHOWN_SCREENS)["shown"]),
                           **_page_overflow(page),
                           "small_targets": page.evaluate(JS_TARGETS, t["min_target_px"]),
                           "small_targets_44": page.evaluate(JS_TARGETS, t["mobile_target_px"]) if vw <= 480 else [],
                           "small_text": page.evaluate(JS_TEXT, t["min_text_px"]), "focus_missing": [],
                           "focus_obscured": [], "text_spacing_clipped": []}
                    for v in _axe(page, tags):
                        rep["axe"].append({**v, "screen": scr["id"], "viewport": vw})
                    page.screenshot(path=str(shots / f"{scr['id']}-{vw}.png"), full_page=True)
                    row["tiles"] = _tiles(page, shots, f"{scr['id']}-{vw}", vw)
                    seen = set()
                    # instant scroll, as the obscured-focus walk has: a smooth-scrolling view still had a chart point
                    # below the fold when it was read, and its indicator went unread (refresh field run)
                    page.evaluate("() => {" + JS_INSTANT_SCROLL + "}")
                    for _ in range(int(t["focus_sample"])):
                        page.evaluate(JS_ARM_MUT)
                        page.keyboard.press("Tab")
                        f = page.evaluate(JS_FOCUS)
                        if not f:
                            continue
                        key = f["uid"]
                        if key in seen:
                            break
                        seen.add(key)
                        if not f["visible"] and not _focus_drawn(page):
                            row["focus_missing"].append(f)
                    page.evaluate("() => { if (window.__pdgObs) window.__pdgObs.disconnect(); window.__pdgObs = null; "
                                  "window.__pdgMut = []; }")   # the walk's observer records nothing after it
                    row["focus_obscured"] = _focus_obscured(page, int(t.get("focus_obscured_sample", 60)))
                    # only what the spacing causes: an ellipsis or a decorative overflow there before it is not a 1.4.12
                    # failure (audit #3). Clipping at the widest width, as before; what else the spacing breaks (text
                    # past its box, a cut select value, page overflow, a word broken mid-word) at every width (W56)
                    # clipping (the adopted 1.4.12 reading) and the other spacing readings fail apart: an error in the
                    # latter does not leave clipping unmeasured (review S-b)
                    plain = None
                    try:
                        before = {_clip_key(x): _clip_px(x) for x in page.evaluate(JS_TEXT_SPACING, 400)} if vw == widest else {}
                        try:
                            plain = page.evaluate(JS_BAND)
                        except Exception as exc:  # noqa: BLE001
                            row["text_spacing_error"] = str(exc).splitlines()[0][:160]
                        page.add_style_tag(content=TEXT_SPACING_STYLE)
                        page.wait_for_timeout(20)
                        if vw == widest:
                            row["text_spacing_clipped"] = [x for x in page.evaluate(JS_TEXT_SPACING, 400)
                                                           if _spacing_clips(x, before.get(_clip_key(x)))][:20]
                    except Exception as exc:  # noqa: BLE001 - clipping unread at the widest fails 1.4.12
                        row.update(text_spacing_error=str(exc).splitlines()[0][:160], text_spacing_widest=vw == widest)
                    if plain is not None and "text_spacing_widest" not in row:
                        try:
                            row.update(_spacing_breaks(plain, page.evaluate(JS_BAND)))
                        except Exception as exc:  # noqa: BLE001 - named in RESP-TEXT, not fatal
                            row["text_spacing_error"] = str(exc).splitlines()[0][:160]
                    if vw == widest:
                        page.goto("about:blank")          # the spacing style above must not change what the tokens resolve to
                        page.goto(_url(entry, scr["route"]))
                        _settle(page)
                        rep["tokens"].append({"screen": scr["id"], "viewport": vw,
                                              **_token_report(page, tokens or {}, int(t.get("token_rules_max", 3000)),
                                                              entry.parent)})
                    rep["screens"].append(row)
                _everywhere(rep, vw)
                for stt in states:
                    page.goto("about:blank")
                    page.goto(_url(entry, stt["route"]))
                    _settle(page)
                    try:
                        page.locator(stt["marker"]).first.wait_for(state="visible", timeout=timeout)
                        ok = True
                    except Exception:  # noqa: BLE001 - the state did not render: that is the finding
                        ok = False
                    row = {"screen": stt["screen"], "state": stt["state"], "viewport": vw, "rendered": ok}
                    _forbidden(page, forbidden, f"{stt['screen']}#{stt['state']}", vw, rep)
                    if ok:
                        for v in _axe(page, tags):
                            rep["axe"].append({**v, "screen": f"{stt['screen']}#{stt['state']}", "viewport": vw})
                        page.screenshot(path=str(shots / f"{stt['screen']}-{stt['state']}-{vw}.png"), full_page=True)
                    if ok and vw == widest:   # the screen holds still with focus in it (B-09); once, at the widest width
                        row["watch"] = _watch_state(page, stt["marker"], int(t.get("state_hold_ms", 1000)), timeout)
                        rep["tokens"].append({"screen": f"{stt['screen']}#{stt['state']}", "viewport": vw,
                                              **_token_report(page, tokens or {}, int(t.get("token_rules_max", 3000)),
                                                              entry.parent)})
                    if ok and stt.get("recover"):
                        row["recovered"] = _recover(page, stt, timeout)
                    rep["states"].append(row)
                ctxb.close()
            rep["samples_cut"] = {}
            picked = sample_routes(screens, links, int(t.get("sample_routes_max", 24)), cut=rep["samples_cut"])
            if picked:
                _beat(f"checking {sum(len(v) for v in picked.values())} sampled records render their screens")
            design_shows = {r["screen"]: set(r["shows"]) for r in rep["screens"] if viewports and r["viewport"] == viewports[0]}
            renders = {r["screen"] for r in rep["screens"] if r.get("renders_screen")}   # the screens worth waiting for
            samples, rep["samples_dropped"] = _rendering_samples(browser, entry, picked, viewports[0] if viewports else 1280,
                                                                 min(timeout, 2000), design_shows)
            rep["samples"] = samples
            # and below the narrowest planned width, down to one step above the reflow width (320 px is the reflow pass's):
            # 321–389 px are phones too, and nothing else reads them (W53). Up to 5 widths; the planned grid is unchanged
            step = int(t.get("band_step_px", 20))
            band = band_widths(viewports, step)
            if band and step > 0:
                band = sorted(set(_spread(list(range(int(t["reflow_px"]) + step, band[0], step)), 5)) | set(band))
            if band:
                n = sum(len(v) for v in samples.values())
                _beat(f"width band {band[0]}–{band[-1]} px every {t.get('band_step_px', 20)} px: {len(screens)} screens"
                      + (f", {n} sampled records" if n else ""))
                _band(browser, entry, screens, band, rep, samples=samples, planned=viewports,
                      budget_s=float(t.get("sample_budget_s", 90)), renders=renders, wait_ms=min(timeout, 2000))
            if viewports:
                phones = sorted({w for w in band if w <= min(min(viewports), 480)} | {int(t["reflow_px"])})   # review N2
                _beat(f"chosen values: each select's longest option at {phones[0]}–{phones[-1]} px")
                _chosen(browser, entry, screens, phones, rep, renders, min(timeout, 2000),
                        budget_s=float(t.get("chosen_budget_s", 90)))
                _beat(f"interactive states against the status colours at {max(viewports)} px")
                _state_fills(browser, entry, screens, max(viewports), rep, renders, min(timeout, 2000), status or {},
                             budget_s=float(t.get("state_budget_s", 60)), click_budget_s=float(t.get("state_click_budget_s", 60)))
            if reference:
                widths = sorted({min(viewports), max(viewports)}) if viewports else []
                _beat(f"reference parity at {widths} px against {Path(reference['entry']).name}")
                _parity(browser, entry, reference, screens, widths, rep)
            _beat(f"reflow at {t['reflow_px']} px, then reduced motion")
            ctxb = browser.new_context(viewport={"width": t["reflow_px"], "height": 640})
            page = ctxb.new_page()
            col.attach(page, "reflow@320")
            for scr in screens:
                for route in [scr["route"], *samples.get(scr["id"], [])]:
                    row: dict[str, Any] = {"screen": scr["id"], "route": route, "sample": route != scr["route"]}
                    try:
                        page.goto("about:blank")
                        page.goto(_url(entry, route), timeout=3 * timeout)
                        _settle(page)
                        if route != scr["route"] or scr["id"] in renders:
                            _await_screen(page, scr["id"], min(timeout, 2000))
                        row.update(_page_overflow(page))
                    except Exception as exc:  # noqa: BLE001 - a route that will not load is named, not fatal (W53 review I4)
                        row.update(overflow_px=0, error=str(exc).splitlines()[0][:160])
                        try:
                            page.close()
                        except Exception:  # noqa: BLE001 - a crashed renderer: the context closes it
                            pass
                        page = ctxb.new_page()
                        col.attach(page, "reflow@320")
                    rep["reflow_320"].append(row)
            ctxb.close()
            ctxb = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
            page = ctxb.new_page()
            col.attach(page, "reduced-motion")
            for scr in screens:
                page.goto(_url(entry, scr["route"]))
                _settle(page)
                for m in page.evaluate(JS_MOTION, t["reduced_motion_max_s"]):
                    rep["reduced_motion"].append({**m, "screen": scr["id"]})
            ctxb.close()
        finally:
            browser.close()
    rep["console"], rep["requests"] = col.console, col.requests
    write_json_atomic(out / "browser-report.json", rep)
    return rep


def findings_from(rep: dict[str, Any], t: dict[str, Any], res: CheckResult) -> None:
    """Turn a suite report into per-dimension verdicts with traced findings."""
    if rep.get("scrollbars"):   # shown in the reviewer's packet, which judges screenshots (field run W19)
        res.messages.append(f"screenshots: scrollbars are {rep['scrollbars']}")
    fails = [s for s in rep["scenarios"] if not s["passed"]]
    shown: dict[tuple[str, str], list[int]] = {}
    for h in rep.get("forbidden_text", []):
        shown.setdefault((h["where"], h["text"]), []).append(h["viewport"])
    res.dim("FUNC-SCENARIOS", not fails and not shown,
            f"{len(rep['scenarios']) - len(fails)}/{len(rep['scenarios'])} scenario runs passed"
            + (f"; forbidden text shown {len(shown)} time(s)" if shown else
               f"; forbidden text: none of {len(rep['forbidden_checked'])} shown" if rep.get("forbidden_checked") else ""),
            [finding("FUNC-SCENARIOS", f"{s['id']} fails at {s['viewport']} px: {s['error']}", "P2", f"{s['id']}:{s['viewport']}",
                     IMPL, f"make {s['id']} step {s['failed_step']} succeed", f"{s['id']} passes at {s['viewport']} px")
             for s in fails]
            + [finding("FUNC-SCENARIOS", f"{where} shows the forbidden text {text!r} at {sorted(set(vws))} px", "P2",
                       f"{where}#forbidden:{text[:40]}", IMPL, f"remove {text!r} from what {where} renders",
                       f"no screen or state shows {text!r} at any planned viewport") for (where, text), vws in shown.items()])
    missing = [s for s in rep["states"] if not s["rendered"]]
    swept = sorted({r["screen"] for r in rep["screens"]})
    off_route: dict[str, dict[str, Any]] = {}
    for r in rep["screens"]:
        if not r.get("renders_screen", True):   # reports written before the check have no field: not measured
            o = off_route.setdefault(r["screen"], {"route": r.get("route", "?"), "viewports": []})
            o["viewports"].append(r["viewport"])
            if r.get("renders_why"):
                o["why"] = r["renders_why"]
    res.dim("FUNC-STATES", not missing and not off_route,
            f"{len(rep['states']) - len(missing)}/{len(rep['states'])} planned states rendered; "
            f"{len(swept) - len(off_route)}/{len(swept)} screen routes render their screen",
            [finding("FUNC-STATES", f"state {s['screen']}#{s['state']} did not render its marker at {s['viewport']} px", "P2",
                     f"{s['screen']}#{s['state']}", IMPL, "render the planned state and its marker",
                     f"the {s['state']} marker is visible on {s['screen']}") for s in missing]
            + [finding("FUNC-STATES", f"screen {sid}: its route {o['route']} does not render [data-screen=\"{sid}\"] in a "
                       f"fresh session at {o['viewports']} px" + (f" ({o['why']})" if o.get("why") else "")
                       + ", so the sweep measured another page", "P2", sid, IMPL,
                       "make the route render its screen in a fresh session (seed the record it names), or correct the "
                       "route in the information architecture (N07)",
                       f"[data-screen=\"{sid}\"] is visible at {o['route']} in a fresh session") for sid, o in off_route.items()])
    unstable, stuck, unfocused = [], [], []   # (screen, where, message)
    for r in rep["states"]:
        w, where = r.get("watch") or {}, f"{r['screen']}#{r['state']}@{r['viewport']}"
        if w.get("error"):
            unstable.append((r["screen"], where, f"could not be watched ({w['error']})"))
        elif w.get("left"):
            unstable.append((r["screen"], where, "the page navigated away while the state was watched"))
        elif w:
            why = []
            if w.get("held") is False:
                why.append(f"focus on {w.get('control')} was lost")
            if not w.get("busy") and w.get("changes", 0) > t.get("state_max_changes", 10):
                why.append(f"{w['changes']} elements added or removed in {w.get('hold_ms')} ms")
            if w.get("live", 0) > t.get("state_max_live", 1):
                why.append(f"{w['live']} live regions inserted in {w.get('hold_ms')} ms")
            if why:
                unstable.append((r["screen"], where, "; ".join(why)))
            if w.get("control") is None:
                unfocused.append(where)
        if r.get("recovered") and not r["recovered"]["ok"]:
            stuck.append((r["screen"], where, f"pressing {r['recovered']['click']} did not end the state "
                                              f"({r['recovered']['error']})"))
    if unstable or stuck:
        res.dim("FUNC-STATES", False,
                "; ".join((["states that do not hold still: " + "; ".join(f"{w}: {m}" for _, w, m in unstable[:6])]
                           if unstable else [])
                          + (["ways back that do nothing: " + "; ".join(f"{w}: {m}" for _, w, m in stuck[:6])] if stuck else [])),
                findings=[finding("FUNC-STATES", f"{w}: {m}", "P1", scr, IMPL,
                                  "keep the state's DOM still once rendered; wire its way back",
                                  "the state holds focus for a second, and its way back ends it")
                          for scr, w, m in (unstable + stuck)[:20]])
    if unfocused:   # said, so a pass never implies a focus check that did not run (review S4)
        res.dim("FUNC-STATES", True, f"note: no control to focus, so focus was not watched, in {len(unfocused)} state(s): "
                + ", ".join(unfocused[:8]))
    rows = rep.get("tokens", [])
    toks = [(r, u) for r in rows for u in r["undefined"]]
    offs = [(r, m) for r in rows for m in r["mismatched"]]
    blind = [f"{r['screen']}: {r['error']}" for r in rows if r.get("error")] + sorted(
        {f"{r['screen']}: stylesheet {h} could not be read" for r in rows for h in r.get("unreadable_sheets", [])})
    containers = max((r.get("containers", 0) for r in rows), default=0)   # the same rules on every page: not a sum
    rejected = max((r.get("rejected", 0) for r in rows), default=0)
    uncompared = sorted({n for r in rows for n in r.get("not_compared", [])})
    res.dim("VIS-TOKENS-RUNTIME", not toks and not offs and not blind,
            f"{len(rows)} screens and states read" + (": every token used resolves, and every design-system colour "
                                                       "defined matches" if not toks and not offs and not blind else "")
            + ("; undefined where used: " + ", ".join(sorted({f"{u['name']} ({u['where']})" for _, u in toks})[:10])
               if toks else "")
            + ("; differs from the design system: " + ", ".join(sorted({f"{m['name']} = {m['build']} (system "
                                                                     f"{m['system']})" for _, m in offs})[:10]) if offs else "")
            + (f"; not measured (an unmeasured MUST is not a pass): {'; '.join(blind[:5])}" if blind else "")
            + (f"; note: not judged: {containers} @container group(s), whose condition depends on the element"
               if containers else "")
            + (f"; note: not judged: {rejected} rule(s) whose selector the browser rejects" if rejected else "")
            + (f"; note: not compared, in a colour space the check cannot read: {', '.join(uncompared[:8])}"
               if uncompared else ""),
            findings=[{**finding("VIS-TOKENS-RUNTIME", f"{u['name']} is undefined on {u['elements']} element(s) matching "
                                 f"{u['where']}, so the declaration using it is dropped", "P1", r["screen"], IMPL,
                                 f"define {u['name']} (a token defined as itself is undefined)",
                                 f"getComputedStyle reads {u['name']} on {u['where']}"), "element": u["where"]}
                      for r, u in toks[:20]]
            + [{**finding("VIS-TOKENS-RUNTIME", f"--{m['name']} is {m['build']}; the design system says {m['system']}",
                          "P2", r["screen"], IMPL, f"set --{m['name']} to the design system's value",
                          f"--{m['name']} computes to {m['system']}"), "element": f"--{m['name']}"} for r, m in offs[:20]])
    step = rep.get("band_step", 20)
    over: dict[str, list[int]] = {}
    over_in: dict[Any, set[str]] = {}      # a screen → the region around its view that scrolled sideways (R2-27)
    words: dict[tuple[str, str, str], list[int]] = {}
    spills: dict[tuple[str, str], list[int]] = {}
    band_blind, restless, resize_only = [], [], 0
    select_cuts: dict[tuple[str, str], dict[str, Any]] = {}   # a select that cuts its value, or would an option's (W55)
    cut_notes: set[str] = set()
    on: dict[Any, set[str]] = {}           # a problem → the sampled records it was seen on (W53)

    def seen_on(key: Any, r: dict[str, Any]) -> None:
        if r.get("sample"):
            on.setdefault(key, set()).add(r["route"])

    def records(key: Any) -> str:
        rs = sorted(on.get(key, ()))
        shown = ", ".join(_short(x) for x in rs[:3]) + (", …" if len(rs) > 3 else "")
        return f" (on sampled record{'s' if len(rs) > 1 else ''} {shown})" if rs else ""
    for r in rep.get("band", []):
        if r.get("error"):
            band_blind.append(f"{r['screen']}: {r['error']}")
            continue
        if r.get("restless"):
            restless.append(f"{r['screen']}@{r['width']}" + (f" ({_short(r['route'])})" if r.get("sample") else ""))
        faked = r.get("resize_only") or {}
        if (faked.get("overflow", 0) > 1 or faked.get("midword") or faked.get("spill")) and not (
                r.get("overflow", 0) > 1 or r.get("midword") or r.get("spill")):
            resize_only += 1   # what the resize faked cleared on a fresh load (a cut select is not a resize reading)
        if r["overflow"] > 1:
            over.setdefault(r["screen"], []).append(r["width"])
            if r.get("overflow_in"):
                over_in.setdefault(r["screen"], set()).add(r["overflow_in"])
            seen_on(r["screen"], r)
        for m in r["midword"]:
            words.setdefault((r["screen"], m["word"], m["el"]), []).append(r["width"])
            seen_on((r["screen"], m["word"], m["el"]), r)
        for x in r["spill"]:
            spills.setdefault((r["screen"], x["el"]), []).append(r["width"])
            seen_on((r["screen"], x["el"]), r)
        for x in r.get("cut", []):
            c = select_cuts.setdefault((r["screen"], x["el"]), {"shown": [], "option": [], "shown_text": "", "option_text": ""})
            kind = "shown" if x.get("shown", True) else "option"
            c[kind].append(r["width"])
            c[kind + "_text"] = c[kind + "_text"] or x["text"]
            seen_on(("cut", r["screen"], x["el"]), r)
        if r.get("cut_note"):
            cut_notes.add(r["cut_note"])
    over = {k: sorted(set(v)) for k, v in over.items()}
    # two elements with one label are one finding per width; every problem is a finding, in a fixed order, so a live one
    # is never cut by a count (W53 review I3); only the evidence text is cut
    words = {k: sorted(set(v)) for k, v in sorted(words.items())}
    spills = {k: sorted(set(v)) for k, v in sorted(spills.items())}
    swept = sorted({r["width"] for r in rep.get("band", []) if r.get("width")})
    # what 1.4.12 text spacing breaks at a planned width that was not broken without it (W56). Read here, advisory, until
    # Wei amends the adopted rule behind A11Y-TEXT-SPACING-1412, which reads clipping only (review I4)
    spaced: dict[tuple[str, str, str, str], set[int]] = {}      # (what, element, text, screen) → widths

    def spacing(what: str, el: str, text: str, r: dict[str, Any]) -> None:
        spaced.setdefault((what, el, text, r["screen"]), set()).add(r["viewport"])
    spacing_unread = []
    for r in rep["screens"]:
        for x in r.get("text_spacing_spill", []):
            spacing("runs past its box", x["el"], "", r)
        for x in r.get("text_spacing_cut", []):
            spacing("cuts its value" if x.get("shown", True) else "would cut its option", x["el"], x["text"], r)
        for m in r.get("text_spacing_midword", []):
            spacing("breaks a word mid-word", m["el"], m["word"], r)
        if r.get("text_spacing_overflow"):
            spacing("overflows the page", "page", "", r)
        if r.get("text_spacing_error"):
            spacing_unread.append(f"{r['screen']}@{r['viewport']}")

    # a select with an id on two or more swept screens is part of the shared shell: one finding at `shell`, wherever it
    # is cut, so its identity holds while a fix reaches some screens first; anything else is one finding per screen
    # (review IB)
    present_on: dict[str, set[str]] = {}
    for r in rep.get("band", []):
        for el in r.get("selects", []):
            present_on.setdefault(el, set()).add(r["screen"])

    def id_of(el: str) -> str:
        return el.split(".", 1)[0] if el.startswith("select#") else el

    def loc_of(scr: str, el: str) -> str:
        return "shell" if len(present_on.get(id_of(el), ())) >= 2 else scr

    def on_screens(loc: str, el: str, scrs: list[str]) -> str:
        if loc != "shell":
            return ""
        return (f" (cut on {len(scrs)} of {len(present_on[id_of(el)])} screens: {', '.join(scrs[:4])}"
                f"{', …' if len(scrs) > 4 else ''})")
    cut_groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for scr, el in sorted(select_cuts):
        loc = loc_of(scr, el)
        cut_groups.setdefault((loc, id_of(el) if loc == "shell" else el), []).append((scr, el))
    cut_rows = []                     # (location, element, message)
    for (loc, el), members in cut_groups.items():
        scrs = [scr for scr, _ in members]
        cs = [select_cuts[m] for m in members]
        shown = sorted({w for c in cs for w in c["shown"]})
        option = sorted({w for c in cs for w in c["option"]})
        parts = ([f"shows '{next(c['shown_text'] for c in cs if c['shown_text'])}' cut at {_ranges(shown, swept)}"]
                 if shown else []) + ([f"its option '{next(c['option_text'] for c in cs if c['option_text'])}' would be "
                                       f"cut at {_ranges(option, swept)}"] if option else [])
        recs = sorted(set().union(*(on.get(("cut", scr, e), set()) for scr, e in members)))
        rec_note = (f" (on sampled record{'s' if len(recs) > 1 else ''} {', '.join(_short(x) for x in recs[:3])}"
                    f"{', …' if len(recs) > 3 else ''})") if recs else ""
        cut_rows.append((loc, el, f"{loc}: {el} {'; '.join(parts)}{on_screens(loc, el, scrs)}{rec_note}"))
    spaced_groups: dict[tuple[str, str, str], dict[str, set]] = {}
    for (what, el, text, scr), widths in spaced.items():
        loc = loc_of(scr, el)
        g = spaced_groups.setdefault((loc, what, id_of(el) if loc == "shell" else el),
                                     {"screens": set(), "widths": set(), "texts": set()})
        g["screens"].add(scr)
        g["widths"] |= widths
        if text:
            g["texts"].add(text)
    spaced_rows = []                  # (location, element, message)
    for (loc, what, el), g in sorted(spaced_groups.items()):
        subject = "" if el == "page" else f" {el}"
        quoted = (" " + ", ".join(f"'{x}'" for x in sorted(g["texts"])[:3])) if g["texts"] else ""
        spaced_rows.append((loc, f"{el} ({what} under 1.4.12 spacing)",
                            f"{loc}:{subject} {what}{quoted} under 1.4.12 text spacing at "
                            f"{', '.join(map(str, sorted(g['widths'])))} px{on_screens(loc, el, sorted(g['screens']))}"))
    if step <= 0:
        band_blind.append(f"band_step_px is {step}: the band was not swept")
    span = f"{swept[0]}–{swept[-1]} px every {step} px" if swept else "no width"
    notes = ((f"; note: {resize_only} reading(s) flagged only while resizing, clear on a fresh load (not counted)"
              if resize_only else "")
             + (f"; note: never quiet within 1 s, read anyway: {', '.join(restless[:6])}" if restless else ""))
    # a screen with a select's longest value chosen, read at the phone widths (field run W58). The pass reads each screen
    # as loaded (`default`), with the disclosures that hide a select open (`opened`), and with each value chosen
    # (`chosen`); each state counts only what it adds to the one before it at the same width, under the same spacing
    # (a choice behind a disclosure: to the opened screen; the opened screen: to the default one). The chosen select's
    # own cut is W55's option cut (W58 replay: D-214's panel, and the band's missing 320 px reading)
    reflow_at = {r["screen"]: r for r in rep.get("reflow_320", []) if not r.get("sample") and not r.get("error")}
    phones = rep.get("chosen_widths") or []
    rows = [r for r in rep.get("chosen", []) if r.get("width")]
    base_at = {(r["screen"], r["width"], r["state"], bool(r.get("spacing"))): r for r in rows if r.get("state") != "chosen"}
    chosen_over: dict[tuple[str, str], list[int]] = {}
    chosen_text: dict[tuple[str, str, str, str, str], list[int]] = {}
    phrase: dict[str, str] = {}            # a state (a choice, or disclosures open) → how a finding says it
    unconfirmed: list[str] = []
    read_only = 0

    def group(r: dict[str, Any]) -> tuple[Any, ...]:
        return r["screen"], r.get("state"), r.get("select"), r.get("value")
    cleared = {group(r) for r in rows if r.get("confirmed") and r.get("resize_overflow", 0) > 1 and r["overflow"] <= 1}
    chosen_errors = [f"{r['screen']}{' ' + r['select'] if r.get('select') else ''}: {r['error']}"
                     for r in rep.get("chosen", []) if r.get("error")]
    for r in rows:
        if r.get("state") == "default":
            continue
        opened = " and ".join(r.get("opened") or [])
        if r.get("state") == "opened":
            state, before_state = f"{opened} open", "default"
            phrase[state] = f"once {opened} {'are' if len(r['opened']) > 1 else 'is'} open"
        else:
            state, before_state = f"{r['select']} = '{r['value']}'", "opened" if opened else "default"
            phrase[state] = f"once {r['select']} shows '{r['value']}'" + (f" (with {opened} open)" if opened else "")
        key, base = (r["screen"], state), base_at.get((r["screen"], r["width"], before_state, bool(r.get("spacing")))) or {}
        if r.get("spacing"):
            had = ({("spill", x["el"]) for x in base.get("text_spacing_spill", [])}
                   | {("cut", x["el"], x.get("text")) for x in base.get("text_spacing_cut", [])}
                   | {("midword", m["el"], m["word"]) for m in base.get("text_spacing_midword", [])})
            what = ([("overflows the page under 1.4.12 spacing", "page", "")]
                    if r.get("text_spacing_overflow") and not base.get("text_spacing_overflow") else [])
            what += [("runs past its box under 1.4.12 spacing", x["el"], "") for x in r.get("text_spacing_spill", [])
                     if ("spill", x["el"]) not in had]
            what += [("cuts its value under 1.4.12 spacing" if x.get("shown", True) else "would cut its option under 1.4.12 spacing",
                      x["el"], x.get("text", "")) for x in r.get("text_spacing_cut", [])
                     if x["el"] != r["select"] and ("cut", x["el"], x.get("text")) not in had]
            what += [("breaks a word mid-word under 1.4.12 spacing", m["el"], m["word"]) for m in r.get("text_spacing_midword", [])
                     if ("midword", m["el"], m["word"]) not in had]
        else:
            # a confirmed overflow is judged against the state before it, read fresh too (review S2); one never tried counts
            # as read, as in the band, unless a fresh load cleared the same state at another width; one whose confirmation
            # failed is named, not counted (review S1, R2)
            before = r["base_overflow"] if "base_overflow" in r else base.get("overflow", reflow_at.get(r["screen"], {}).get("overflow_px", 0))
            dropped = r.get("confirm_error") or (None if r.get("confirmed") else
                                                 "a fresh load cleared it at another width" if group(r) in cleared else None)
            if r.get("overflow", 0) > 1 and before <= 1 and not dropped:
                chosen_over.setdefault(key, []).append(r["width"])
                if r.get("overflow_in"):
                    over_in.setdefault(key, set()).add(r["overflow_in"])
                read_only += 0 if r.get("confirmed") else 1
            elif r.get("overflow", 0) > 1 and before <= 1:
                unconfirmed.append(f"{r['screen']} at {r['width']} px {phrase[state]} ({dropped})")
            # a box keeps its identity when a choice changes its text (review S3)
            had = ({("spill", x["el"]) for x in base.get("spill", [])}
                   | {("cut", x["el"], x.get("text")) for x in base.get("cut", [])}
                   | {("midword", m["el"], m["word"]) for m in base.get("midword", [])})
            what = [("runs past its box", x["el"], "") for x in r.get("spill", []) if ("spill", x["el"]) not in had]
            what += [("cuts its value" if x.get("shown", True) else "would cut its option", x["el"], x.get("text", ""))
                     for x in r.get("cut", [])
                     if x["el"] != r["select"] and ("cut", x["el"], x.get("text")) not in had]
            what += [("breaks a word mid-word", m["el"], m["word"]) for m in r.get("midword", [])
                     if ("midword", m["el"], m["word"]) not in had]
        for kind, el, text in what:
            chosen_text.setdefault((r["screen"], kind, el, text, state), []).append(r["width"])
    chosen_over = {k: sorted(set(v)) for k, v in sorted(chosen_over.items())}
    chosen_text = {k: sorted(set(v)) for k, v in sorted(chosen_text.items())}
    tried = len({(r["screen"], r["select"], r["value"]) for r in rows if r["state"] == "chosen"})
    behind = sorted({o for r in rows for o in r.get("opened") or []})
    hidden = rep.get("chosen_hidden") or {}
    # a disclosure that leaves the screen or cannot be clicked is named; one that revealed nothing (an accordion's other
    # groups) is common and harmless, so it is counted per screen
    left_closed = sorted((rep.get("chosen_toggles") or {}).items())
    toggles = [f"{sid}: {n} ({why})" for sid, bad in left_closed for n, why in sorted(bad.items()) if why != "revealed no select"]
    quiet = [f"{sid} {n}" for sid, bad in left_closed if (n := sum(1 for why in bad.values() if why == "revealed no select"))]
    capped = rep.get("chosen_capped") or {}
    chosen_note = ((f"; {tried} select value(s) chosen and read at {phones[0]}–{phones[-1]} px" if tried and phones else "")
                   + (f", with {', '.join(behind[:3])} opened to reach them" if behind else "")
                   + (f" ({rep['chosen_unread']} not read: the time budget ran out)" if rep.get("chosen_unread") else "")
                   + (f" ({rep['chosen_unread_screens']} screen(s) not read: the time budget ran out)"
                      if rep.get("chosen_unread_screens") else "")
                   + (f"; note: at most {rep.get('chosen_per_screen', 6)} selects chosen per screen ({', '.join(f'{k} has {n}' for k, n in sorted(capped.items())[:3])})"
                      if capped else "")
                   + (f"; note: disclosures left closed: {'; '.join(toggles[:4])}"
                      + (f" and {len(toggles) - 4} more" if len(toggles) > 4 else "") if toggles else "")
                   + (f"; note: disclosures that revealed no select: {', '.join(quiet[:6])}" if quiet else "")
                   + (f"; note: {read_only} overflow reading(s) with a value chosen were past the confirmation cap or "
                      "time and count as read" if read_only else "")
                   + (f"; note: overflow with a value chosen not counted: {'; '.join(unconfirmed[:3])}" if unconfirmed else "")
                   + (f"; note: selects hidden at {phones[-1]} px were not chosen ("
                      + ", ".join(f"{n} on {s}" for s, n in sorted(hidden.items())[:4]) + ")" if hidden and phones else "")
                   + (f"; note: not read with a value chosen: {'; '.join(chosen_errors[:3])}" if chosen_errors else ""))
    res.dim("RESP-BAND", not over and not band_blind and not chosen_over,
            f"{len({r['screen'] for r in rep.get('band', []) if r.get('width')})} screens swept at {span}"
            + ("; no page overflow as loaded" if not over and not band_blind else "")
            + (f"; plus {rep['band_samples']['routes']} sampled record(s) at {len(rep['band_samples']['widths'])} widths"
               if rep.get("band_samples") else "")
            + (f" ({rep['band_samples']['unread']} not read: the samples' time budget ran out)"
               if (rep.get("band_samples") or {}).get("unread") else "")
            + ("; page overflows: " + "; ".join(f"{scr} at {_ranges(ws, swept)}{records(scr)}{_inside(over_in.get(scr))}"
                                                for scr, ws in over.items())
               if over else "")
            + ("; page overflows with a value chosen: " + "; ".join(
                f"{scr} at {_ranges(ws, phones)} {phrase[st]}{_inside(over_in.get((scr, st)))}"
                for (scr, st), ws in list(chosen_over.items())[:6])
               if chosen_over else "")
            + (f"; not measured: {'; '.join(band_blind[:4])}" if band_blind else "") + notes + chosen_note,
            findings=[finding("RESP-BAND", f"{scr} overflows the page horizontally at {_ranges(ws, swept)}{records(scr)}"
                              f"{_inside(over_in.get(scr))}", "P2", scr, IMPL,
                              "let the layout reflow at those widths (a min-width, a fixed track or a nowrap run)",
                              f"no horizontal page scroll on {scr} anywhere in the band") for scr, ws in over.items()]
            + [{**finding("RESP-BAND", f"{scr} overflows the page horizontally at {_ranges(ws, phones)} {phrase[st]}"
                          f"{_inside(over_in.get((scr, st)))}", "P2", scr, IMPL,
                          "let what the chosen value or the opened panel widens (a chip, a panel, a label) wrap or shrink "
                          "at phone widths",
                          f"no horizontal page scroll on {scr} at any phone width, {phrase[st]}"),
                "element": st} for (scr, st), ws in chosen_over.items()])
    # where each is, first: 22 findings on one line could not be triaged by screen (field run 2, 19:30Z note)
    per_screen = Counter([k[0] for k in words] + [k[0] for k in spills] + [loc for loc, _, _ in cut_rows]
                         + [loc for loc, _, _ in spaced_rows] + [k[0] for k in chosen_text])
    res.dim("RESP-TEXT", not words and not spills and not cut_rows and not spaced_rows and not chosen_text,
            f"text read at {span}"
            + (f"; {sum(per_screen.values())} findings by screen: " + ", ".join(f"{s} {n}" for s, n in per_screen.most_common())
               if per_screen else "")
            + ("; no word broken mid-word, no boxed text past its box, no select that cuts its value, "
                                      "and nothing 1.4.12 spacing breaks"
                                      if not words and not spills and not cut_rows and not spaced_rows and not chosen_text else "")
            + ("; broken mid-word: " + "; ".join(f"{scr}: '{w}' in {el} at {_ranges(ws, swept)}" for (scr, w, el), ws in list(words.items())[:8])
               if words else "")
            + ("; past its box: " + "; ".join(f"{scr}: {el} at {_ranges(ws, swept)}" for (scr, el), ws in list(spills.items())[:8])
               if spills else "")
            + ("; selects: " + "; ".join(m for _, _, m in cut_rows[:8]) if cut_rows else "")
            + ("; " + "; ".join(m for _, _, m in spaced_rows[:8]) if spaced_rows else "")
            + (f"; note: selects not measured ({'; '.join(sorted(cut_notes))})" if cut_notes else "")
            + (f"; note: not read under 1.4.12 spacing: {', '.join(spacing_unread[:6])}" if spacing_unread else "")
            + ("; with a value chosen: " + "; ".join(
                f"{scr}: {'' if el == 'page' else el + ' '}{kind}{' ' + repr(text) if text else ''} at {_ranges(ws, phones)} "
                f"{phrase[st]}" for (scr, kind, el, text, st), ws in list(chosen_text.items())[:6]) if chosen_text else "")
            + notes,
            findings=[{**finding("RESP-TEXT", f"{scr}: '{w}' breaks mid-word in {el} at {_ranges(ws, swept)}"
                                 f"{records((scr, w, el))}", "P2", scr, IMPL,
                                 "give the container room at those widths, or allow hyphenation (hyphens: auto)",
                                 f"'{w}' stays on one line on {scr} across the band"), "element": el}
                      for (scr, w, el), ws in words.items()]
            + [{**finding("RESP-TEXT", f"{scr}: {el} runs past its box at {_ranges(ws, swept)}{records((scr, el))}", "P2", scr, IMPL,
                          "let the text wrap inside its box, or size the box to its content at those widths",
                          f"{el} stays inside its box on {scr} across the band"), "element": el}
               for (scr, el), ws in spills.items()]
            + [{**finding("RESP-TEXT", msg, "P2", loc, IMPL,
                          "size the select to the values it can show at those widths (a wider track, or field-sizing: "
                          "content with a max-width), or shorten the values",
                          f"{el} shows its whole value, and every option's, across the band"), "element": el}
               for loc, el, msg in cut_rows]
            + [{**finding("RESP-TEXT", msg, "P2", loc, IMPL,
                          "let the box grow with its text under 1.4.12 spacing (no fixed width or height on text, no nowrap "
                          "on a label), or allow hyphenation",
                          "under 1.4.12 text spacing, nothing on the screen loses content or breaks a word"), "element": el}
               for loc, el, msg in spaced_rows]
            + [{**finding("RESP-TEXT", f"{scr}: {'' if el == 'page' else el + ' '}{kind}{' ' + repr(text) if text else ''} at "
                          f"{_ranges(ws, phones)} {phrase[st]}", "P2", scr, IMPL,
                          "let what the chosen value or the opened panel widens wrap or grow with its text at phone widths",
                          f"{phrase[st]}, nothing on {scr} loses content or breaks a word at a phone width"),
                "element": f"{el} ({kind} with {st})"} for (scr, kind, el, text, st), ws in chosen_text.items()])
    # R2-26: an interactive state in a status colour, a status mark a state repaints, a hover heavier than the choice.
    # A status colour is the design system's (by role) or a fill that varies across a list's marks: it encodes data
    found: dict[tuple[str, str, str], str] = {}
    orders: list[str] = []
    groups_read = 0
    documented = rep.get("state_documented") or {}
    as_documented: dict[str, None] = {}   # a state the design system fills with a status colour on purpose (R2-26 addendum)
    hovered = sum(1 for r in rep.get("state_fills", []) for g in r.get("groups", []) if g.get("hover"))
    fills_unread = [f"{r['screen']}: {r['error']}" for r in rep.get("state_fills", []) if r.get("error")]
    fills_unread += [f"{r['screen']} {g['list']} > {g['el']}: not hovered ({g['hover_error']})"
                     for r in rep.get("state_fills", []) for g in r.get("groups", []) if g.get("hover_error")]
    for r in rep.get("state_fills", []):
        for g in r.get("groups", []):
            groups_read += 1
            item = f"{g['list']} > {g['el']}"   # two lists whose current items share a label stay apart (review S5)
            names_at = {c: [n] if isinstance(n, str) else list(n) for c, n in r["status"].items()}   # one colour, its names
            table = {**{c: f"the status colour {' / '.join(n)}" for c, n in names_at.items()},
                     **{c: f"a colour the list's {k} marks carry for their data" for c, k in g["data"].items() if c not in r["status"]}}

            def meaning(f: str | None) -> str | None:
                return next((n for c, n in table.items() if _near(c, f)), None) if f else None

            def documented_for(f: str | None, what: str, own: set[str]) -> str | None:
                """This item's state, in a colour the design system documents for one of its own classes (the item
                read: the current one, or the resting one hovered; a report without them skips nothing)."""
                who = f"{g['list']} > {g.get('rest_el') or g['el']} when hovered" if what == "hovered" else item
                return next((f"{r['screen']} {who}: {n} is the design "
                             "system's state fill for " + ", ".join(f".{k}" for k in sorted(own & set(documented[n])))
                             for c, names in names_at.items() if f and _near(c, f)
                             for n in names if own & set(documented.get(n, []))), None)

            def add(problem: str, text: str) -> None:
                found[(r["screen"], item, problem)] = text
            hover = g.get("hover") or {}
            cur = g["current"] if _rgba(g["current"]) else None
            # a hover that changes nothing is no hover state (review I1)
            hov = hover.get("fill") if _rgba(hover.get("fill")) and not _near(hover.get("fill"), g["rest"]) else None
            # rows filled by their data (a status per row) are coloured so whatever is chosen (review I1)
            for f, what, own in ((cur, "current", set(g.get("cls") or [])), (hov, "hovered", set(g.get("rest_cls") or []))):
                if (note := documented_for(f, what, own)):
                    as_documented[note] = None
                elif f and meaning(f) and (what == "hovered" or not any(_near(f, x) for x in g.get("rest_fills", []))):
                    add(f"{what} fill", f"the {what} item fills {f}, {meaning(f)}")
            hover_marks = hover.get("marks", [])
            for n, m in enumerate(g["rest_marks"]):
                if not meaning(m["fill"]):
                    continue
                twin = _twin(m, g["current_marks"])   # the same slot in the current item
                cm = twin["fill"] if twin else None
                if cm and cur and _near(cm, cur):
                    add(f"{m['key']} when current", f"{twin['el']} takes the current item's own fill {cur}, so its colour vanishes")
                elif cm and not meaning(cm) and (_grey(cm) or _near(cm, g["surface"])):   # a band a row alone carries is
                    add(f"{m['key']} when current",                                         # a colour (review S2)
                        f"{twin['el']} loses its colour in the current item ({cm})")
                hm = hover_marks[n] if n < len(hover_marks) else None   # the same element, hovered (review I6)
                if hm and hov and _near(hm, hov):
                    add(f"{m['key']} when hovered", f"{m['el']} takes the hovered item's own fill {hov}, so its colour vanishes")
                elif hm and not _near(hm, m["fill"]):
                    add(f"{m['key']} when hovered", f"{m['el']} changes its fill from {m['fill']} to {hm} when its item is hovered")
            if cur and hov:
                rc, rh = (_ratio(_on(x, g["surface"]), g["surface"]) for x in (cur, hov))
                orders.append(f"{r['screen']} {item}: hover {rh:.2f}:1, current {rc:.2f}:1")
                if rh > rc + 0.01:
                    add("hover heavier", f"a hovered item ({hov}, {rh:.2f}:1 on its surface) reads heavier than the current "
                                         f"one ({cur}, {rc:.2f}:1), so it looks like a second choice")
    width = max(rep.get("viewports") or [0])
    res.dim("VIS-STATE-FILLS", not found,
            f"{groups_read} list(s) of items with a current, selected or pressed one read at {width} px"
            + (("; " + "; ".join(f"{s}: {el}: {t}" for (s, el, _), t in list(found.items())[:6])) if found
               else "; no state takes a status colour and every status mark keeps its colour"
               + (", and hover reads no heavier than the current item" if hovered else "")
               if groups_read else "")   # an empty pass claims nothing (review S6)
            + (f"; hover and current against their surface: {'; '.join(orders[:4])}" if orders else "")
            + (f"; documented, not judged: {'; '.join(list(as_documented)[:4])}"
               + (f" and {len(as_documented) - 4} more" if len(as_documented) > 4 else "") if as_documented else "")
            + (f" ({rep['state_fills_unread']} screen(s) not read: the time budget ran out)" if rep.get("state_fills_unread") else "")
            + (f"; not read: {'; '.join(fills_unread[:3])}" if fills_unread else ""),
            [{**finding("VIS-STATE-FILLS", f"{scr}: {el}: {text}", "P3", scr, IMPL,
                        "mark the current item with the design system's 'where you are' mark (a bar, a ring) on a light fill "
                        "that is no status colour; keep every status mark's fill in every state; make hover lighter than "
                        "the current item",
                        f"on {scr}, no current, selected or hovered item takes a status colour, every status mark keeps its "
                        "colour in every state, and hover reads no heavier than the current item"), "element": f"{el} ({problem})"}
             for (scr, el, problem), text in found.items()])
    # R2-29: after a click, focus on a redrawn copy of what was clicked, or a focus ring a pointer user sees
    pointer: dict[tuple[str, str, str], str] = {}
    clicked, left = 0, 0
    click_errors = [f"{r['screen']}: {r['click_error']}" for r in rep.get("state_fills", []) if r.get("click_error")]
    for r in rep.get("state_fills", []):
        for g in r.get("groups", []):
            c = g.get("click")
            if not c:
                continue
            if c.get("error") or c.get("skipped"):
                click_errors.append(f"{r['screen']} {g['list']} > {g['el']}: {c.get('error') or c['skipped']}")
                continue
            if c.get("left"):   # the click went to another screen: nothing here to judge (review I4)
                left += 1
                continue
            clicked += 1
            if c.get("copy"):
                pointer[(r["screen"], f"{g['list']} > {g['el']}", "refocused copy")] = (
                    f"clicking an item redraws it and puts focus on its copy ({c['active']}) by script; a pointer user's "
                    "browser may draw the focus ring on what they clicked")
            if c.get("ring"):
                pointer[(r["screen"], f"{g['list']} > {g['el']}", "ring")] = (
                    f"after a click on an item, {c['active']} in the list matches :focus-visible, so a pointer user sees the "
                    "focus ring")
    res.dim("A11Y-FOCUS-POINTER", not pointer,
            f"{clicked} list item(s) clicked at {max(rep.get('viewports') or [0])} px"
            + ("; no click left focus on a redrawn copy or showed a focus ring in its list" if clicked and not pointer else "")
            + (f"; {left} click(s) went to another screen (not judged)" if left else "")
            + ("; " + "; ".join(f"{s}: {el}: {t}" for (s, el, _), t in list(pointer.items())[:4]) if pointer else "")
            + (f"; not clicked: {'; '.join(click_errors[:3])}" if click_errors else ""),
            [{**finding("A11Y-FOCUS-POINTER", f"{scr}: {el}: {text}", "P3", scr, IMPL,
                        "update the clicked item in place on selection, so it keeps its own focus; never refocus a redrawn "
                        "copy by script after a pointer click",
                        f"on {scr}, after a click on an item, focus is on the node clicked and nothing matches :focus-visible"),
              "element": f"{el} ({problem})"} for (scr, el, problem), text in pointer.items()])
    if rep.get("reference_error"):
        res.dim("REF-PARITY", False, f"not measured: {rep['reference_error']}")
    elif rep.get("reference") is None and rep.get("reference_hint"):   # a refresh with its reference on disk (R2-25)
        res.dim("REF-PARITY", False, f"a reference build is in the sources ({rep['reference_hint']}) but not declared: "
                                     "name it in `reference:` in pdg.project.yaml, or this check compares nothing")
    elif rep.get("reference") is None:
        res.dim("REF-PARITY", True, "no reference build declared (`reference:` in pdg.project.yaml): nothing to compare")
    else:
        expected = rep.get("reference_expected") or []

        def intended(screen: str, prop: str) -> str | None:
            return next((x["reason"] for x in expected if x["property"] == prop and x.get("screen", "*") in ("*", screen)),
                        None)
        drifts, meant, blind, skipped, restless = [], [], [], [], []
        for r in rep.get("parity", []):
            where = f"{r['screen']}@{r['viewport']}"
            if r.get("skipped"):
                skipped.append(f"{where} ({r['skipped']})")
            elif r.get("error") or not r.get("reference"):
                blind.append(f"{where}: {r.get('error') or 'not read'}")
            else:
                for prop, d in parity_drifts(r["build"], r["reference"], t):
                    why = intended(r["screen"], prop)
                    (meant if why else drifts).append((r["screen"], where, d + (f" — intended: {why}" if why else "")))
                if r.get("restless"):
                    restless.append(f"{where} ({', '.join(r['restless'])})")
        blocked = rep.get("parity_blocked") or {}
        res.dim("REF-PARITY", not drifts and not blind,
                f"{len(rep.get('parity', []))} screen×width pairs against {Path(rep['reference']).name}"
                + ("; no unexplained drift" if not drifts and not blind else "")
                + ("; drift: " + "; ".join(f"{w}: {d}" for _, w, d in drifts[:12]) if drifts else "")
                + (f"; not compared: {'; '.join(blind[:5])}" if blind else "")
                + ("; note: intended (reference.expected): " + "; ".join(f"{w}: {d}" for _, w, d in meant[:8]) if meant else "")
                + (f"; note: skipped {', '.join(skipped[:8])}" if skipped else "")
                + (f"; note: never quiet within 3 s, read anyway: {', '.join(restless[:6])}" if restless else "")
                + (f"; note: non-local requests blocked on both sides alike: {blocked}" if blocked else ""),
                findings=[finding("REF-PARITY", f"{w}: {d}", "P2", scr, IMPL,
                                  "keep what the reference does, or list the change in `reference.expected` with its reason",
                                  f"{w} matches the reference on this property") for scr, w, d in drifts[:20]])
    res.dim("FUNC-CONSOLE", not rep["console"], f"{len(rep['console'])} console/page errors",
            [finding("FUNC-CONSOLE", f"console error: {c['text']}", "P2", c["where"].split("@")[0], IMPL,
                     "fix the script error", "0 console errors") for c in rep["console"][:5]])
    res.dim("FUNC-OFFLINE", not rep["requests"], f"{len(rep['requests'])} requests outside file:/data:",
            [finding("FUNC-OFFLINE", f"network request {r}", "P2", "network", IMPL, "inline or remove the resource",
                     "0 requests outside the prototype") for r in rep["requests"][:5]])
    dcl = [x["dcl"] for x in rep["timing_ms"] if x["dcl"] is not None]
    worst = max(dcl) if dcl else 0
    res.dim("PERF-LOAD", worst <= t["load_budget_ms"], f"worst DOMContentLoaded {worst:.0f} ms (budget {t['load_budget_ms']} ms)")
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    for v in rep["axe"]:
        k = (str(v["screen"]), v["id"])
        a = agg.setdefault(k, {"impact": v["impact"], "help": v["help"], "viewports": set(), "nodes": v["nodes"]})
        a["viewports"].add(v["viewport"])
    sev = {"critical": "P1", "serious": "P2", "moderate": "P3", "minor": "P3"}
    res.dim("A11Y-AXE", not agg, f"{len(agg)} distinct axe violations" + (": " + ", ".join(f"{r}@{s}" for s, r in sorted(agg)) if agg else ""),
            [finding("A11Y-AXE", f"axe {rid} ({a['impact']}) on {scr} at {sorted(a['viewports'])} px: {a['help']}",
                     sev.get(a["impact"], "P3"), f"{scr}:{rid}", IMPL,
                     f"{a['help']}; first node {a['nodes'][0]['target'] if a['nodes'] else '?'}: "
                     f"{(a['nodes'][0]['summary'] if a['nodes'] else '').splitlines()[0] if a['nodes'] else ''}",
                     f"axe reports 0 '{rid}' violations on {scr} at every viewport",
                     evidence="; ".join(n["target"] for n in a["nodes"]))
             for (scr, rid), a in sorted(agg.items())])
    foc = [(r["screen"], f) for r in rep["screens"] for f in r["focus_missing"]]
    res.dim("A11Y-FOCUS", not foc, f"{len(foc)} focused controls without a visible indicator",
            [finding("A11Y-FOCUS", f"no visible focus on {f['tag']} '{f['text']}'", "P2", scr, IMPL,
                     "give every focusable control a :focus-visible outline", "every tab stop shows a focus ring")
             for scr, f in foc[:8]])
    obscured = [(r["screen"], r["viewport"], x) for r in rep["screens"] for x in r.get("focus_obscured", [])]
    by_focus_loc: dict[str, list] = {}
    for scr, vw, x in obscured:
        by_focus_loc.setdefault(f"{scr}:{vw}", []).append(x)
    res.dim("A11Y-FOCUS-VISIBLE-2411", not obscured, f"{len(obscured)} focus stops wholly obscured",
            [finding("A11Y-FOCUS-VISIBLE-2411", f"{loc.split(':')[0]} at {loc.split(':')[1]} px has {len(xs)} focus "
                     f"stop(s) wholly obscured, e.g. {', '.join(_label(x) + ' via ' + x['direction'] + (' (covered by ' + x['cover'] + ')' if x.get('cover') else ' (off-screen after focus: the page scrolled it away)' if x.get('offscreen') else ' (clipped by ' + x['clip'] + ': scrolled out of its container)' if x.get('clip') else '') for x in xs[:3])}",
                     "P2", loc, IMPL,
                     "add scroll-padding-top/scroll-margin-top for sticky chrome or move the focused control out from "
                     "under overlapping content",
                     f"Tab and Shift+Tab through {loc}: no sampled focus rect is wholly hidden",
                     evidence=", ".join(_label(x) for x in xs[:5])) for loc, xs in by_focus_loc.items()])
    small = [(r["screen"], r["viewport"], x) for r in rep["screens"] for x in r["small_targets"]]
    by_loc: dict[str, list] = {}
    for scr, vw, x in small:
        by_loc.setdefault(f"{scr}:{vw}", []).append(x)
    res.dim("A11Y-TARGET-AA", not small, f"{len(small)} targets below {t['min_target_px']} px",
            [finding("A11Y-TARGET-AA", f"{len(xs)} targets below {t['min_target_px']} px, e.g. {xs[0]['tag']} "
                     f"'{xs[0]['text']}' {xs[0]['w']}×{xs[0]['h']}", "P2", loc, IMPL,
                     f"give these controls ≥ {t['min_target_px']} × {t['min_target_px']} px (padding or min-height)",
                     f"0 targets below {t['min_target_px']} px on {loc}") for loc, xs in by_loc.items()])
    small44 = [(r["screen"], r["viewport"], x) for r in rep["screens"] for x in r["small_targets_44"]]
    res.dim("A11Y-TARGET-44", not small44, f"{len(small44)} mobile targets below {t['mobile_target_px']} px",
            [finding("A11Y-TARGET-44", f"{len(small44)} mobile targets below {t['mobile_target_px']} px", "P4", "mobile", IMPL,
                     f"raise mobile targets to {t['mobile_target_px']} px", "0 small mobile targets")] if small44 else [])
    txt = [(r["screen"], r["viewport"], x) for r in rep["screens"] for x in r["small_text"]]
    res.dim("A11Y-TYPE-MIN", not txt, f"{len(txt)} text elements below {t['min_text_px']} px",
            [finding("A11Y-TYPE-MIN", f"text '{x['text']}' at {x['size']} px", "P3", f"{scr}:{vw}", IMPL,
                     f"use a type token ≥ {t['min_text_px']} px", f"0 text below {t['min_text_px']} px") for scr, vw, x in txt[:6]])
    clipped = [(r["screen"], r["viewport"], x) for r in rep["screens"] for x in r.get("text_spacing_clipped", [])]
    by_text_loc: dict[str, list] = {}
    for scr, vw, x in clipped:
        by_text_loc.setdefault(f"{scr}:{vw}", []).append(x)
    # clipping at the widest width, as the adopted rule R-A11Y-007 says; what else the spacing breaks is read into
    # RESP-TEXT until Wei amends the rule (W56; review I4). Clipping that could not be read is not a pass
    unread = [f"{r['screen']}@{r['viewport']}: {r['text_spacing_error']}" for r in rep["screens"]
              if r.get("text_spacing_error") and r.get("text_spacing_widest")]
    res.dim("A11Y-TEXT-SPACING-1412", not clipped and not unread, f"{len(clipped)} text elements clipped under 1.4.12 spacing"
            + (f"; not measured: {'; '.join(unread[:4])}" if unread else ""),
            [finding("A11Y-TEXT-SPACING-1412", f"{loc.split(':')[0]} at {loc.split(':')[1]} px has {len(xs)} clipped "
                     f"text element(s) after 1.4.12 spacing, e.g. {', '.join(_label(x) for x in xs[:3])}",
                     "P2", loc, IMPL,
                     "remove fixed heights/line clamps or let the text container wrap and expand under WCAG text spacing",
                     f"after applying 1.4.12 spacing on {loc}, no text element scrolls beyond a hidden/clip overflow box",
                     evidence=", ".join(_label(x) for x in xs[:5])) for loc, xs in by_text_loc.items()])
    res.dim("A11Y-REDUCED-MOTION", not rep["reduced_motion"], f"{len(rep['reduced_motion'])} elements animate > "
            f"{t['reduced_motion_max_s']} s under reduced motion")
    over = [r for r in rep["screens"] if r["overflow_px"] > 1]
    res.dim("RESP-OVERFLOW", not over, f"{len(over)} screen×viewport with horizontal overflow",
            [finding("RESP-OVERFLOW", f"{r['screen']} overflows by {r['overflow_px']} px at {r['viewport']} px"
                     f"{_inside(r.get('overflow_in'))}", "P2",
                     f"{r['screen']}:{r['viewport']}", IMPL, "let the layout wrap or scroll inside its own region",
                     f"no horizontal overflow on {r['screen']} at {r['viewport']} px") for r in over])
    # one finding per screen, naming the records that overflow when more than its own route was loaded (W53)
    loaded: dict[str, int] = {}
    wide: dict[str, list[dict[str, Any]]] = {}
    unread = [r for r in rep["reflow_320"] if r.get("error")]
    for r in rep["reflow_320"]:
        if r.get("error"):
            continue
        loaded[r["screen"]] = loaded.get(r["screen"], 0) + 1
        if r["overflow_px"] > 1:
            wide.setdefault(r["screen"], []).append(r)
    extra = sum(1 for r in rep["reflow_320"] if r.get("sample") and not r.get("error"))
    blind = [r for r in unread if not r.get("sample")]              # a design route not read is not a pass
    dropped = rep.get("samples_dropped") or {}
    unread_text = "; ".join(f"{r['screen']} {_short(r.get('route') or '#')}: {r['error']}" for r in unread[:4])
    dropped_text = "; ".join(f"{k} " + ", ".join(_short(x) for x in v[:3]) for k, v in dropped.items())
    cut = rep.get("samples_cut") or {}
    cut_text = "; ".join(f"{k} " + ", ".join(_short(x) for x in v[:3]) for k, v in cut.items())

    def where(scr: str) -> str:
        rs = wide[scr]
        if loaded[scr] == 1:
            return ""
        routes = [_short(r.get("route", "?")) for r in sorted(rs, key=lambda r: -r["overflow_px"])]
        return f" on {len(rs)} of {loaded[scr]} routes loaded ({', '.join(routes[:4])}{', …' if len(routes) > 4 else ''})"
    res.dim("RESP-REFLOW-320", not wide and not blind, f"{len(wide)} screens overflow at 320 px"
            + (f" ({extra} sampled route(s) also loaded)" if extra else "")
            + (f"; not read: {unread_text}" if unread else "")
            + (f"; samples dropped, they do not render their screen alone: {dropped_text}" if dropped else "")
            + (f"; plan samples not read, over their screen's share of the {int(t.get('sample_routes_max', 24))}-route "
               f"cap: {cut_text}" if cut else ""),
            [finding("RESP-REFLOW-320", f"{scr} overflows by {max(r['overflow_px'] for r in rs)} px at 320 px{where(scr)}"
                     f"{_inside({r['overflow_in'] for r in rs if r.get('overflow_in')})}", "P2",
                     f"{scr}:320", IMPL, "restack the layout below 400 px",
                     f"no page-level horizontal scroll on {scr} at 320 px, on every record") for scr, rs in wide.items()])


# the words a colour's name or role opens with for a status (the field runs: "alert: held, failed and destructive status
# text", "watch fill, paired with amber-ink", "completed fill", "warning pill background", status-green). Only the role's
# leading label counts: "hover and selected rows; never a status colour" names no status (review I4)
STATUS_WORDS = ("alert", "alerts", "warning", "warnings", "success", "error", "errors", "danger", "critical", "caution",
                "status", "severity", "risk", "watch", "completed", "flag", "flags", "held", "failed", "blocked", "overdue",
                "pending", "positive", "negative")
STATUS_ROLE = re.compile(r"^\W*(" + "|".join(STATUS_WORDS) + r")\b", re.I)


def documented_state_fills(colors: list[Any]) -> dict[str, list[str]]:
    """The design system's own state fills: colour name → the component classes whose state it fills on purpose."""
    return {c.name: list(c.state_fill_of) for c in colors if getattr(c, "state_fill_of", None)}


def status_colours(colors: list[Any]) -> dict[str, str]:
    """The design system's status colours, name → #rrggbb: a colour whose role opens with a status, or whose name has a
    status word in it (status-green, alertRed, status_red) (R2-26)."""
    def words(name: str) -> set[str]:
        return {w.lower() for w in re.split(r"[-_\s]+|(?<=[a-z])(?=[A-Z])", name) if w}
    return {c.name: c.value for c in colors if STATUS_ROLE.search(c.role) or words(c.name) & set(STATUS_WORDS)}


def _reference_hint(ctx: NodeContext) -> str | None:
    """A built reference in `sources/references/` that `reference:` does not name (field run 2, R2-25)."""
    root = getattr(getattr(getattr(ctx, "engine", None), "project", None), "root", None)
    return reference_hint_for(Path(root)) if root else None


def reference_hint_for(root: Path) -> str | None:
    refs = root / "sources" / "references"
    if not refs.is_dir():
        return None
    found = next((p for p in sorted(refs.rglob("*.html")) if p.is_file()), None)
    return str(found.relative_to(root)) if found else None


def _reference(ctx: NodeContext) -> dict[str, Any] | None:
    project = getattr(getattr(ctx, "engine", None), "project", None)
    return reference_for(Path(project.root), getattr(project, "config", None) or {}) if project is not None else None


def reference_for(root: Path, config: dict[str, Any]) -> dict[str, Any] | None:
    """The reference build a refresh must keep parity with (`reference:` in pdg.project.yaml; N-28), its entry resolved
    against the project. A declared reference that is missing or malformed is an error on REF-PARITY, never a silent
    pass and never the whole suite (review I2)."""
    ref = config.get("reference")
    if not ref:
        return None
    if not isinstance(ref, dict) or not isinstance(ref.get("entry"), str):
        raise ValueError("`reference` needs `entry: <path to the reference build's entry html>`")
    routes = ref.get("routes") or {}
    if not isinstance(routes, dict) or not all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in routes.items()):
        raise ValueError("`reference.routes` maps a screen id to its route in the reference, or to null to skip it")
    expected = ref.get("expected") or []
    if not isinstance(expected, list) or not all(isinstance(x, dict) and x.get("property") in PARITY_PROPERTIES
                                                 and str(x.get("reason", "")).strip() for x in expected):
        raise ValueError("each `reference.expected` entry needs `property` (one of " + ", ".join(PARITY_PROPERTIES)
                         + "), a `reason`, and optionally `screen`")
    entry = Path(ref["entry"]).expanduser()
    entry = entry if entry.is_absolute() else root / entry
    if not entry.is_file():
        raise FileNotFoundError(f"the reference build's entry {entry} does not exist (`reference.entry` in pdg.project.yaml)")
    return {"entry": str(entry), "routes": dict(routes), "expected": list(expected)}


def note_reference(rep: dict[str, Any], out: Path, error: str | None, hint: str | None) -> None:
    """The report N13 reads says why REF-PARITY compared nothing, not just "no reference" (review S4)."""
    if error or hint:
        rep.update({k: v for k, v in (("reference_error", error), ("reference_hint", hint)) if v})
        write_json_atomic(out / "browser-report.json", rep)


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    try:
        import playwright  # noqa: F401
    except ImportError:
        res.errors.append("Playwright is not installed in this Python environment (pip install playwright)")
        res.data["blocked"] = "playwright unavailable"
        return res
    if not axe_path().is_file():
        res.errors.append(f"axe-core not found at {axe_path()} (set PDG_AXE_PATH)")
        res.data["blocked"] = "axe-core unavailable"
        return res
    try:
        reference, reference_error = _reference(ctx), None
    except (OSError, KeyError, TypeError, ValueError) as exc:   # a misdeclared reference fails REF-PARITY, not the suite
        reference, reference_error = None, str(exc)
    root = ctx.artifact("prototype")
    man = json.loads((root / "build-manifest.json").read_text())
    entry = root / man["entry"]
    plan = ctx.state.build.plan
    t = ctx.thresholds["browser"]
    scenarios = [s.model_dump() for s in plan.scenarios] if plan else []
    states = [s.model_dump() for s in plan.states] if plan else []
    screens = suite_screens([s.model_dump() for s in ctx.state.design.screens], plan.samples if plan else {})
    viewports = (plan.viewports if plan and plan.viewports else t["viewports"])
    out = ctx.work
    try:
        system = ctx.state.design.system
        rep = run_suite(entry, scenarios, states, screens, viewports, t, out,
                        forbidden=list(plan.forbidden_text) if plan else None,
                        tokens={c.name: c.value for c in system.colors} if system else {},
                        reference=reference, status=status_colours(system.colors) if system else {},
                        documented=documented_state_fills(system.colors) if system else {})
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:300]
        res.errors.append(f"the browser suite could not run: {msg}")
        if re.search(r"Executable doesn't exist|browserType.launch|Host system is missing", msg):
            res.data["blocked"] = "Chromium unavailable"
        return res
    hint = None if reference or reference_error else _reference_hint(ctx)
    note_reference(rep, out, reference_error, hint)
    findings_from(rep, t, res)
    res.outputs["browser_report"] = str(out / "browser-report.json")
    res.outputs["screenshots"] = str(out / "screenshots")
    runs = len(rep["scenarios"])
    passed = sum(1 for s in rep["scenarios"] if s["passed"])
    res.data["test_results"] = [{"suite": f"browser scenarios × {len(viewports)} viewports", "passed": passed,
                                 "failed": runs - passed, "details": f"axe violations: {len(rep['axe'])}; console: "
                                 f"{len(rep['console'])}; requests: {len(rep['requests'])}"}]
    return res
