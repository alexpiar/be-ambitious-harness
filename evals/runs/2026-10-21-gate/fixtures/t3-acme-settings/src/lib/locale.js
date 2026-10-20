'use strict';

// Locale strings arrive from the shells as BCP 47 tags, e.g. "en-US".
function languageOf(locale) {
  return locale.split('-')[0].toLowerCase();
}

function regionOf(locale) {
  const parts = locale.split('-');
  return parts[1].toUpperCase();
}

module.exports = { languageOf, regionOf };
