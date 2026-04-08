import eslint from '@eslint/js';
import typescript from '@typescript-eslint/eslint-plugin';
import typescriptParser from '@typescript-eslint/parser';
import svelte from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';

export default [
  // 排除 build 產物、套件、以及 Svelte 5 runes 模組（*.svelte.ts/js 由 svelte-check 負責）
  {
    ignores: ['.svelte-kit/**', 'build/**', 'node_modules/**', '**/*.svelte.ts', '**/*.svelte.js']
  },
  eslint.configs.recommended,
  // JS/TS 檔案共用設定
  {
    files: ['**/*.{js,ts}'],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        sourceType: 'module',
        ecmaVersion: 2020
      },
      globals: {
        console: 'readonly',
        document: 'readonly',
        window: 'readonly',
        navigator: 'readonly',
        fetch: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        FormData: 'readonly',
        File: 'readonly',
        Response: 'readonly',
        Headers: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        process: 'readonly',
        HTMLElement: 'readonly'
      }
    },
    plugins: {
      '@typescript-eslint': typescript
    },
    rules: {
      // 關閉 base 版本，改用 TS 版本避免誤報
      'no-shadow': 'off',
      'no-redeclare': 'off',
      'no-unused-vars': 'off',
      'no-undef': 'off',                         // TypeScript 編譯器負責檢查
      'no-implicit-globals': 'error',
      'prefer-const': 'error',

      // TypeScript 規則
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-shadow': 'error',
      '@typescript-eslint/no-redeclare': 'error'
      // 命名約定由 npm run check:naming 負責
    }
  },
  ...svelte.configs['flat/recommended'],
  // Svelte 檔案設定
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parser: svelteParser,
      parserOptions: {
        parser: typescriptParser,
        extraFileExtensions: ['.svelte']
      }
    },
    rules: {
      // 關閉 base 版本，Svelte 編譯器與 TypeScript 負責檢查
      'no-unused-vars': 'off',
      'no-undef': 'off',
      // Svelte 特定規則
      'svelte/no-unused-svelte-ignore': 'error',
      // 專案未設定 paths.base，resolve() 為 no-op，停用此規則避免無意義的包裝
      'svelte/no-navigation-without-resolve': 'off'
    }
  }
];