// Где старый парсер не падал, но новый отвечает иначе — чтобы честно назвать изменения поведения
'use strict';
const oldP = require(process.argv[2] + '/src/lib/locale');
const newP = require(process.argv[3] + '/src/lib/locale');
const tags = ['en-US','de-DE','EN-gb','en_US','de_DE','zh-Hant-TW','sr-Latn-RS','es-419','de-DE-u-co-phonebk','123-US','root-US','en-USA','en-',' en-US','en-US ','iw-IL','en-UK','x-foo-US'];
let seed = 7; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
const abc = 'aAzZ09-_ x'; for (let n = 0; n < 20000; n++) { let s = ''; const len = 1 + Math.floor(rnd() * 8); for (let k = 0; k < len; k++) s += abc[Math.floor(rnd() * abc.length)]; tags.push(s); }
const cls = {};
for (const t of tags) {
  let o; try { o = [oldP.languageOf(t), oldP.regionOf(t)]; } catch (e) { continue; }
  const n = [newP.languageOf(t), newP.regionOf(t)];
  if (o[0] !== n[0] || o[1] !== n[1]) { const k = (o[0] !== n[0] ? 'lang ' : '') + (o[1] !== n[1] ? 'region' : ''); (cls[k] = cls[k] || []).push(`${JSON.stringify(t)}: ${o} -> ${n}`); }
}
for (const [k, v] of Object.entries(cls)) console.log(k, v.length, '\n  ' + v.slice(0, 8).join('\n  '));
