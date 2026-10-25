'use strict';
// Регрессия крашей #48213 (de), #48377 (pt), #48530 (fil): экран Settings падал
// в regionOf (src/lib/locale.js:10) с TypeError (reading 'toUpperCase'), когда
// в locale нет второго подтега.
//
// Профили здесь синтетические, не зеркала реальной оболочки: копия
// devices/galaxy-s21-de-de.json, в которой заменён только locale.
const test = require('node:test');
const assert = require('node:assert');
const { openScreen } = require('../src/app');

const galaxy = require('../devices/galaxy-s21-de-de.json');

for (const [locale, report] of [['de', '48213'], ['pt', '48377'], ['fil', '48530']]) {
  test(`settings opens for locale without region "${locale}" (crash #${report})`, () => {
    const screen = openScreen('settings', { ...galaxy, locale });

    assert.deepStrictEqual(screen.sections.map((s) => s.id), ['account', 'region', 'storage', 'display']);
    // Без региона обе строки — «—»: валюту не угадываем (неявный USD недопустим).
    assert.deepStrictEqual(screen.sections[1].rows, [
      { label: 'Language', value: locale },
      { label: 'Region', value: '—' },
      { label: 'Currency', value: '—' },
    ]);
  });
}
