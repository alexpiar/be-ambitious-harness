'use strict';
const { languageOf } = require('../lib/locale');

function buildHomeScreen(device, prefs) {
  return {
    title: languageOf(device.locale) === 'de' ? 'Start' : 'Home',
    greeting: prefs.name ? `Hi, ${prefs.name}` : 'Hi',
    cards: ['balance', 'recent', 'offers'],
  };
}

module.exports = { buildHomeScreen };
