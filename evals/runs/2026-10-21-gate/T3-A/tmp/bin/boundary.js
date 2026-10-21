// Граничный ввод: openScreen('settings', …) на синтетическом профиле с заданной locale.
// usage: node boundary.js <путь к repo>
'use strict';
const path = require('path');
const repo = path.resolve(process.argv[2]);
const { openScreen } = require(path.join(repo, 'src/app'));
const base = { model: 'Samsung Galaxy S21', os: 'Android 13', locale: 'de-DE', darkMode: false,
  storage: { freeBytes: 9663676416 }, screen: { density: 3 } };
for (const locale of ['pt_BR', 'zh-Hant', 'zh-Hant-TW', 'es-419', 'DE', '', 'de-']) {
  try {
    const s = openScreen('settings', { ...base, locale });
    const rows = s.sections.find((x) => x.id === 'region').rows.map((r) => `${r.label}=${JSON.stringify(r.value)}`).join(' ');
    console.log(`OK    ${JSON.stringify(locale).padEnd(13)} sections=${s.sections.map((x) => x.id).join(',')} ${rows}`);
  } catch (e) {
    const frame = (e.stack.split('\n').find((l) => l.includes(repo + '/src/')) || '').trim().replace(repo + '/', '');
    console.log(`THROW ${JSON.stringify(locale).padEnd(13)} ${e.constructor.name}: ${e.message} @ ${frame}`);
  }
}
