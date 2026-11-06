import js from "@eslint/js";
import pluginVue from "eslint-plugin-vue";
import prettier from "eslint-config-prettier";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "public/", "playwright-report/", "test-results/", "tests/golden/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  // TypeScript resolves globals itself; no-undef does not know the DOM types.
  { files: ["**/*.{ts,vue}"], rules: { "no-undef": "off" } },
  prettier,
);
