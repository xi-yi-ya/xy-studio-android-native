import js from '@eslint/js';
import vue from 'eslint-plugin-vue';
import ts from 'typescript-eslint';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default ts.config(
  { ignores: ['**/node_modules/**', '**/.venv/**', '**/dist/**', '**/build/**', '**/releases/**', '**/local-data/**', '**/prototypes/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...vue.configs['flat/essential'],
  { files: ['**/*.{js,mjs,cjs,ts,vue}'], languageOptions: { globals: { ...globals.browser, ...globals.node } }, rules: { '@typescript-eslint/no-explicit-any': 'warn', '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }] } },
  { files: ['**/*.vue'], languageOptions: { parserOptions: { parser: ts.parser, extraFileExtensions: ['.vue'] } } },
  prettier,
);
