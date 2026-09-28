import js from "@eslint/js";
import vue from "eslint-plugin-vue";
import typescript from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import vueParser from "vue-eslint-parser";

export default [
  js.configs.recommended,
  ...vue.configs["flat/essential"],
  {
    files: ["**/*.ts", "**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: { parser: tsParser, ecmaVersion: "latest", sourceType: "module" },
      globals: { window: "readonly", document: "readonly", localStorage: "readonly", URL: "readonly", CSS: "readonly",
        HTMLElement: "readonly", KeyboardEvent: "readonly", BeforeUnloadEvent: "readonly", Blob: "readonly", Intl: "readonly",
        console: "readonly", fetch: "readonly", setTimeout: "readonly", clearTimeout: "readonly" },
    },
    plugins: { "@typescript-eslint": typescript },
    rules: {
      "vue/multi-word-component-names": "off",
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-console": "warn",
      "no-empty": ["error", { allowEmptyCatch: true }],
    },
  },
  { ignores: ["dist/", "node_modules/", "*.config.js", "tests/"] },
];
