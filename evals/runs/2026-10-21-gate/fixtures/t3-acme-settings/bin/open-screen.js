#!/usr/bin/env node
'use strict';
const fs = require('fs');
const { openScreen } = require('../src/app');

const [name, devicePath] = process.argv.slice(2);
if (!name || !devicePath) {
  console.error('usage: open-screen.js <screen> <device.json>');
  process.exit(2);
}
const device = JSON.parse(fs.readFileSync(devicePath, 'utf8'));
console.log(JSON.stringify(openScreen(name, device), null, 2));
