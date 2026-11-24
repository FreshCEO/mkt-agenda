() => {
  const lum = c => { const a = c.map(v => { v/=255; return v<=.03928 ? v/12.92 : Math.pow((v+.055)/1.055, 2.4); }); return .2126*a[0]+.7152*a[1]+.0722*a[2]; };
  const cr = (a,b) => { const x = lum(a), y = lum(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
  const rgb = s => (s.match(/[\d.]+/g) || []).map(Number);
  const bgOf = el => { while (el){ const cs = getComputedStyle(el); if (el.classList && el.classList.contains('done') && el.classList.contains('node')) return [243,220,154]; const m = rgb(cs.backgroundColor); if (m.length >= 3 && (m.length < 4 || m[3] >= .9)) return m.slice(0,3); el = el.parentElement; } return [201,123,29]; };
  const out = [], seen = new Set(); let minFont = 99, n = 0;
  document.querySelectorAll('body *').forEach(el => {
    if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return;
    const txt = [...el.childNodes].filter(x => x.nodeType === 3 && x.textContent.trim()).map(x => x.textContent.trim()).join(' ');
    if (!txt) return;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || +cs.opacity < .5) return;
    let op = 1, p = el; while (p){ op *= +getComputedStyle(p).opacity; p = p.parentElement; } if (op < .6) return;
    const fs = parseFloat(cs.fontSize), fw = +cs.fontWeight || 400; minFont = Math.min(minFont, fs); n++;
    const c = rgb(cs.color).slice(0,3), ratio = cr(c, bgOf(el)), big = fs >= 24 || (fs >= 18.66 && fw >= 700);
    if (ratio < (big ? 3 : 4.5)){ const key = (el.className || el.tagName) + '|' + cs.color; if (!seen.has(key)){ seen.add(key); out.push({cls: String(el.className || el.tagName).slice(0,40), text: txt.slice(0,24), ratio: +ratio.toFixed(2), fs, color: cs.color}); } }
  });
  return {fails: out, minFont, n};
}