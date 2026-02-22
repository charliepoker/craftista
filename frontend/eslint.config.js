// eslint.config.js
const globals = require("globals");

module.exports = [
  {
    ignores: [
      "**/node_modules/**",
      "**/.nyc_output/**",
      "**/build/**",
      "**/dist/**",
      "**/coverage/**",
      "**/test/**",
    ],
  },
  {
    files: ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2021,
      },
    },
    rules: {
      semi: ["error", "always"],
      quotes: ["error", "single"],
      indent: ["error", 2],
      "comma-dangle": ["error", "always-multiline"],
      "no-unused-vars": "warn",
      "no-console": "off", // Allow console for server-side logging
    },
  },
];
