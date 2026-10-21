// Обзор: как исходный парсер локали ведёт себя на тегах всех форм, сверка с ICU (Intl.Locale)
'use strict';
const path = require('path');
const { languageOf, regionOf } = require(path.resolve(process.argv[2], 'src/lib/locale'));
const A = 'abcdefghijklmnopqrstuvwxyz';
const dn = (type) => new Intl.DisplayNames(['en'], { type, fallback: 'none' });
const langs = [], regions = [];
for (const a of A) for (const b of A) {
  const l = a + b; if (dn('language').of(l) && new Intl.Locale(l).language === l) langs.push(l);
  const r = l.toUpperCase(); if (dn('region').of(r) && new Intl.Locale('und-' + r).region === r) regions.push(r);
}
const tags = new Set();
for (const l of langs) { tags.add(l); for (const r of regions) tags.add(l + '-' + r); }
['zh-Hant-TW','zh-Hans-CN','sr-Latn-RS','sr-Cyrl','uz-Arab-AF','es-419','en-001','de-DE-u-co-phonebk','th-TH-u-nu-thai','ja-JP-u-ca-japanese','en-US-x-twain','ca-ES-valencia','fil','fil-PH','haw-US','yue-HK','en-us','EN-GB','en_US','de_DE',''].forEach((t) => tags.add(t));
let crash = 0, wrong = 0, ok = 0; const ex = { crash: [], wrong: [] };
for (const t of tags) {
  let exp = null; try { const L = new Intl.Locale(t); exp = { lang: L.language, region: L.region || null }; } catch (e) {}
  let got;
  try { got = { lang: languageOf(t), region: regionOf(t) }; } catch (e) { crash++; if (ex.crash.length < 12) ex.crash.push(JSON.stringify(t)); continue; }
  if (exp && (got.lang !== exp.lang || got.region !== exp.region)) { wrong++; if (ex.wrong.length < 12) ex.wrong.push(`${t} -> ${got.lang}/${got.region} (ICU ${exp.lang}/${exp.region})`); }
  else ok++;
}
console.log(`ICU languages(2-letter): ${langs.length}, regions: ${regions.length}, tags: ${tags.size}`);
console.log(`crash: ${crash}, silently wrong: ${wrong}, ok: ${ok}`);
console.log('crash examples:', ex.crash.join(' '));
console.log('wrong examples:\n  ' + ex.wrong.join('\n  '));
