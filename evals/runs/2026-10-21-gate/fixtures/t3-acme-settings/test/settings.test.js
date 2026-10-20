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

test('storage is human readable', () => {
  const storage = openScreen('settings', pixel).sections[2];
  assert.strictEqual(storage.rows[0].value, '45.0 GB');
});

test('home screen title is localized', () => {
  assert.strictEqual(openScreen('home', galaxy).title, 'Start');
});
