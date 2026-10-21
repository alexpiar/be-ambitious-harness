// Аудит пути Настроек: какие входы device роняют openScreen('settings', …).
// usage: node audit.js <путь к repo>
'use strict';
const path = require('path');
const repo = path.resolve(process.argv[2]);
const { openScreen } = require(path.join(repo, 'src/app'));
const base = { model: 'Samsung Galaxy S21', os: 'Android 13', locale: 'de-DE', darkMode: false,
  storage: { freeBytes: 9663676416 }, screen: { density: 3 } };
const omit = (k) => { const d = structuredClone(base); delete d[k]; return d; };
const set = (fn) => { const d = structuredClone(base); fn(d); return d; };
const cases = [
  ['device = undefined', undefined],
  ['device.locale отсутствует', omit('locale')],
  ['device.locale = null', set((d) => { d.locale = null; })],
  ['device.locale = 123 (не строка)', set((d) => { d.locale = 123; })],
  ['device.storage отсутствует', omit('storage')],
  ['device.storage = null', set((d) => { d.storage = null; })],
  ['device.storage.freeBytes отсутствует', set((d) => { delete d.storage.freeBytes; })],
  ['device.storage.freeBytes = null', set((d) => { d.storage.freeBytes = null; })],
  ['device.storage.freeBytes = "100" (строка < 1024)', set((d) => { d.storage.freeBytes = '100'; })],
  ['device.storage.freeBytes = "9663676416" (строка >= 1024)', set((d) => { d.storage.freeBytes = '9663676416'; })],
  ['device.screen отсутствует', omit('screen')],
  ['device.screen = null', set((d) => { d.screen = null; })],
  ['device.screen.density отсутствует', set((d) => { delete d.screen.density; })],
  ['device.screen.density = "3" (строка)', set((d) => { d.screen.density = '3'; })],
  ['device.darkMode отсутствует', omit('darkMode')],
  ['device.model и device.os отсутствуют', set((d) => { delete d.model; delete d.os; })],
];
for (const [name, device] of cases) {
  try {
    const s = openScreen('settings', device);
    const rows = s.sections.map((x) => x.id + ':' + x.rows.map((r) => r.value).join('|')).join(' ');
    console.log(`OK    ${name} -> ${rows}`);
  } catch (e) {
    const frame = e.stack.split('\n').find((l) => l.includes(repo + '/src/')) || '';
    console.log(`THROW ${name} -> ${e.constructor.name}: ${e.message} @ ${frame.trim().replace(repo + '/', '')}`);
  }
}
