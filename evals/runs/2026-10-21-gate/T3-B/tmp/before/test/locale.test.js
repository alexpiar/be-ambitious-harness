'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { languageOf, regionOf } = require('../src/lib/locale');
const { openScreen } = require('../src/app');
const pixel = require('../devices/pixel-7-en-us.json');

test('known tag shapes', () => {
  const cases = [
    // [tag, language, region]
    ['en-US', 'en', 'US'],
    ['de', 'de', null], // crash-48213
    ['pt', 'pt', null], // crash-48377
    ['fil', 'fil', null], // crash-48530
    ['fil-PH', 'fil', 'PH'],
    ['zh-Hant-TW', 'zh', 'TW'],
    ['sr-Latn', 'sr', null],
    ['es-419', 'es', '419'],
    ['de-DE-u-co-phonebk', 'de', 'DE'],
    ['ca-ES-valencia', 'ca', 'ES'],
    ['de-1996', 'de', null],
    ['en-us', 'en', 'US'],
    ['EN-GB', 'en', 'GB'],
    ['en_US', 'en', 'US'],
    ['zh_Hans_CN', 'zh', 'CN'],
    ['', null, null],
    ['-US', null, null],
    ['x-private', null, null],
    [undefined, null, null],
    [null, null, null],
    [42, null, null],
  ];
  for (const [tag, language, region] of cases) {
    assert.strictEqual(languageOf(tag), language, `languageOf(${JSON.stringify(tag)})`);
    assert.strictEqual(regionOf(tag), region, `regionOf(${JSON.stringify(tag)})`);
  }
});

// Outside judge: ICU (Intl.Locale in Node) parses the same tags; we must agree with it.
// Production code can't rely on Intl.Locale (shell runtimes), tests can.
test('agrees with ICU on every language, region and script ICU knows', () => {
  const ABC = 'abcdefghijklmnopqrstuvwxyz';
  const names = {};
  const known = (type, code) => {
    names[type] = names[type] || new Intl.DisplayNames(['en'], { type, fallback: 'none' });
    return names[type].of(code);
  };
  const languages = [];
  const regions = [];
  const scripts = [];
  for (const a of ABC) {
    for (const b of ABC) {
      for (const code of [a + b, ...[...ABC].map((c) => a + b + c)]) {
        if (known('language', code) && new Intl.Locale(code).language === code) languages.push(code);
      }
      const r = (a + b).toUpperCase();
      if (known('region', r) && new Intl.Locale(`und-${r}`).region === r) regions.push(r);
      for (const c of ABC) {
        for (const d of ABC) {
          const s = a.toUpperCase() + b + c + d;
          if (known('script', s)) scripts.push(s);
        }
      }
    }
  }
  for (let n = 0; n < 1000; n += 1) {
    const r = String(n).padStart(3, '0');
    if (known('region', r) && new Intl.Locale(`und-${r}`).region === r) regions.push(r);
  }
  assert.ok(languages.length > 500 && regions.length > 250 && scripts.length > 150, 'ICU data present');

  const suffixes = ['u-nu-latn', 'u-ca-buddhist', 'x-test', 'fonipa', '1996'];
  const random = mulberry32(48213);
  const scrambleCase = (s) => [...s].map((ch) => (random() < 0.5 ? ch.toLowerCase() : ch.toUpperCase())).join('');

  let compared = 0;
  const mismatches = [];
  languages.forEach((lang, i) => {
    const region = regions[i % regions.length];
    const region2 = regions[(i * 7 + 3) % regions.length];
    const script = scripts[i % scripts.length];
    const suffix = suffixes[i % suffixes.length];
    const tags = [
      lang,
      `${lang}-${region}`,
      `${lang}-${script}`,
      `${lang}-${script}-${region2}`,
      `${lang}-${region}-${suffix}`,
      `${lang}-${script}-${region2}-${suffix}`,
      `${lang}-${suffix}`,
    ];
    for (const tag of tags) {
      let icu;
      try {
        icu = new Intl.Locale(tag);
      } catch (e) {
        continue;
      }
      if (icu.toString() !== tag) continue; // ICU replaced an alias; not a parsing question
      const expected = [icu.language, icu.region || null];
      for (const variant of [tag, scrambleCase(tag), tag.replace(/-/g, '_')]) {
        compared += 1;
        const actual = [languageOf(variant), regionOf(variant)];
        if (actual[0] !== expected[0] || actual[1] !== expected[1]) {
          mismatches.push(`${variant}: got ${actual}, ICU ${expected}`);
        }
      }
    }
  });
  assert.ok(compared > 10000, `compared only ${compared} tags`);
  assert.strictEqual(mismatches.length, 0, mismatches.slice(0, 20).join('\n'));
});

test('settings screen opens for any locale value', () => {
  const random = mulberry32(48530);
  const alphabet = 'aAzZ09-_ x';
  const locales = [undefined, null, 0, {}, [], '', '-', '_', '--', 'de-', 'de--DE'];
  for (let n = 0; n < 5000; n += 1) {
    let s = '';
    const len = Math.floor(random() * 12);
    for (let k = 0; k < len; k += 1) s += alphabet[Math.floor(random() * alphabet.length)];
    locales.push(s);
  }
  for (const locale of locales) {
    const screen = openScreen('settings', { ...pixel, locale });
    for (const section of screen.sections) {
      for (const row of section.rows) {
        assert.strictEqual(typeof row.value, 'string', `${row.label} for ${JSON.stringify(locale)}`);
      }
    }
    assert.ok(['Home', 'Start'].includes(openScreen('home', { ...pixel, locale }).title));
  }
});

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
