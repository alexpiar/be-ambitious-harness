'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { openScreen } = require('../src/app');

const pixel = require('../devices/pixel-7-en-us.json');
const iphone = require('../devices/iphone-13-en-gb.json');
const galaxy = require('../devices/galaxy-s21-de-de.json');

test('settings screen has four sections', () => {
  const screen = openScreen('settings', pixel);
  assert.deepStrictEqual(screen.sections.map((s) => s.id), ['account', 'region', 'storage', 'display']);
});

test('region section shows region and currency', () => {
  const region = openScreen('settings', iphone).sections[1];
  assert.strictEqual(region.rows[1].value, 'GB');
  assert.strictEqual(region.rows[2].value, 'GBP');
});

test('german device gets EUR', () => {
  const region = openScreen('settings', galaxy).sections[1];
  assert.strictEqual(region.rows[2].value, 'EUR');
});

// crash-reports/crash-48213.txt, crash-48377.txt, crash-48530.txt: locale without a region
for (const [report, locale] of [['48213', 'de'], ['48377', 'pt'], ['48530', 'fil']]) {
  test(`settings opens for locale "${locale}" (crash #${report})`, () => {
    const region = openScreen('settings', { ...pixel, locale }).sections[1];
    assert.deepStrictEqual(region.rows.map((r) => r.value), [locale, '—', 'USD']);
  });
}

test('script subtag is not taken for the region', () => {
  const region = openScreen('settings', { ...pixel, locale: 'zh-Hant-TW' }).sections[1];
  assert.strictEqual(region.rows[1].value, 'TW');
});

test('storage is human readable', () => {
  const storage = openScreen('settings', pixel).sections[2];
  assert.strictEqual(storage.rows[0].value, '45.0 GB');
});

test('home screen title is localized', () => {
  assert.strictEqual(openScreen('home', galaxy).title, 'Start');
});
