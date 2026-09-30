const preset = require('jest-expo/jest-preset');
module.exports = { ...preset, transformIgnorePatterns: preset.transformIgnorePatterns.map(p=>p.replace('standard-navigation','standard-navigation|intl-messageformat|@formatjs|i18next-icu|test-renderer')),  testMatch:['**/tests/native/*.test.tsx'], setupFilesAfterEnv:['<rootDir>/tests/native/setup.ts'] };
