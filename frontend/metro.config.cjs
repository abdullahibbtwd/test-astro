const { getDefaultConfig } = require('expo/metro-config');
const config = getDefaultConfig(__dirname);
// Fixture regeneration and exported files are server/build artifacts, never app modules.
const existing = config.resolver.blockList;
config.resolver.blockList = [
  ...(Array.isArray(existing) ? existing : existing ? [existing] : []),
  /[/\\]backend[/\\]mock[/\\]fixtures[/\\].*/,
  /[/\\]artifacts[/\\].*/,
  /[/\\]\.local-data[/\\].*/,
];
module.exports = config;
