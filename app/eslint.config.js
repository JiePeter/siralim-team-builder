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
  {
    files: ["src/**/*.vue"],
    ignores: ["src/components/AssetImage.vue"],
    rules: {
      "vue/no-restricted-html-elements": [
        "error",
        { element: "img", message: "Use AssetImage, which resolves the site's base path." },
      ],
    },
  },
  // TypeScript resolves globals itself; no-undef does not know the DOM types.
  { files: ["**/*.{ts,vue}"], rules: { "no-undef": "off" } },
  prettier,
);
