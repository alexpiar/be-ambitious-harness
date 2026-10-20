'use strict';
const { languageOf, regionOf } = require('../lib/locale');
const { formatBytes } = require('../lib/storage');
const { currencyFor } = require('../lib/currency');

function buildSettingsScreen(device, prefs) {
  return {
    title: 'Settings',
    sections: [
      buildAccountSection(prefs),
      buildRegionSection(device),
      buildStorageSection(device),
      buildDisplaySection(device),
    ],
  };
}

function buildAccountSection(prefs) {
  return { id: 'account', rows: [{ label: 'Name', value: prefs.name || '—' }] };
}

function buildRegionSection(device) {
  const region = regionOf(device.locale);
  return {
    id: 'region',
    rows: [
      { label: 'Language', value: languageOf(device.locale) },
      { label: 'Region', value: region },
      { label: 'Currency', value: currencyFor(region) },
    ],
  };
}

function buildStorageSection(device) {
  return {
    id: 'storage',
    rows: [{ label: 'Free space', value: formatBytes(device.storage.freeBytes) }],
  };
}

function buildDisplaySection(device) {
  return {
    id: 'display',
    rows: [
      { label: 'Theme', value: device.darkMode ? 'Dark' : 'Light' },
      { label: 'Scale', value: device.screen.density.toFixed(1) + 'x' },
    ],
  };
}

module.exports = { buildSettingsScreen };
