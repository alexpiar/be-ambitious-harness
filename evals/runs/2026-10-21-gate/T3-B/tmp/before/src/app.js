'use strict';
const { buildHomeScreen } = require('./screens/home');
const { buildSettingsScreen } = require('./screens/settings');

const SCREENS = {
  home: buildHomeScreen,
  settings: buildSettingsScreen,
};

function openScreen(name, device, prefs = {}) {
  const build = SCREENS[name];
  if (!build) {
    throw new Error(`Unknown screen: ${name}`);
  }
  return build(device, prefs);
}

module.exports = { openScreen };
