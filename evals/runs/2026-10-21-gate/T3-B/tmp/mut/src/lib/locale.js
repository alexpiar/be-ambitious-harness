'use strict';

// Locale strings arrive from the shells as BCP 47 tags, e.g. "en-US".
// The region is optional and not always second: "de", "zh-Hant-TW", "es-419",
// "th-TH-u-nu-thai" are all valid (Unicode language id, UTS #35). The platforms' own
// identifiers use "_" ("en_US"), so that separator is accepted too.
// Pure string parsing on purpose: the shells' JS runtimes may lack Intl.Locale.
// Never throws: a part the tag doesn't have comes back as null.

const LANGUAGE = /^(?:[a-z]{2,3})$/i;
const SCRIPT = /^[a-z]{4}$/i;
const REGION = /^(?:[a-z]{2}|[0-9]{3})$/i;

function parseLocale(locale) {
  const none = { language: null, region: null };
  if (typeof locale !== 'string') return none;

  const subtags = locale.trim().split(/[-_]/);
  if (!LANGUAGE.test(subtags[0])) return none;

  let next = subtags[1] || '';
  if (SCRIPT.test(next)) next = subtags[2] || '';
  return {
    language: subtags[0].toLowerCase(),
    region: REGION.test(next) ? next.toUpperCase() : null,
  };
}

function languageOf(locale) {
  return parseLocale(locale).language;
}

// "US", "419", or null when the tag has no region ("de").
function regionOf(locale) {
  return parseLocale(locale).region;
}

module.exports = { languageOf, regionOf };
