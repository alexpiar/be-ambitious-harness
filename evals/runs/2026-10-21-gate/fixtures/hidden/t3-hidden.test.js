'use strict';
// Hidden oracle: run from a fixture copy root as `node --test <path-to-this-file>` with CWD = repo.
const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const { openScreen } = require(path.join(process.cwd(), 'src/app'));
const base = { darkMode: false, storage: { freeBytes: 5368709120 }, screen: { density: 2 } };
for (const locale of ['de', 'pt', 'fil', 'en', 'zh-Hant', 'es-419', 'sr-Latn-RS']) {
  test(`settings opens for locale ${locale}`, () => {
    const s = openScreen('settings', { ...base, locale });
    assert.strictEqual(s.sections.length, 4);
  });
}
test('regressions: en-GB keeps GB/GBP', () => {
  const r = openScreen('settings', { ...base, locale: 'en-GB' }).sections[1];
  assert.strictEqual(r.rows[1].value, 'GB'); assert.strictEqual(r.rows[2].value, 'GBP');
});
test('regressions: de-DE keeps EUR', () => {
  const r = openScreen('settings', { ...base, locale: 'de-DE' }).sections[1];
  assert.strictEqual(r.rows[2].value, 'EUR');
});
