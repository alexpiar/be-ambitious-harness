'use strict';

const BY_REGION = {
  US: 'USD', GB: 'GBP', DE: 'EUR', FR: 'EUR', ES: 'EUR', IT: 'EUR',
  BR: 'BRL', PT: 'EUR', PH: 'PHP', IN: 'INR', JP: 'JPY',
};

function currencyFor(region) {
  return BY_REGION[region] || 'USD';
}

module.exports = { currencyFor };
