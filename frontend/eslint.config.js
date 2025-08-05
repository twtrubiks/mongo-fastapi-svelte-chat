import eslint from '@eslint/js';
import typescript from '@typescript-eslint/eslint-plugin';
import typescriptParser from '@typescript-eslint/parser';
import svelte from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';

export default [
  eslint.configs.recommended,
  {
    files: ['**/*.{js,ts}'],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        sourceType: 'module',
        ecmaVersion: 2020
      },
      globals: {
        browser: true,
        es2017: true,
        node: true
      }
    },
    plugins: {
      '@typescript-eslint': typescript
    },
    rules: {
      // 防止命名衝突的核心規則
      'no-shadow': 'error',                    // 防止變數遮蔽
      'no-redeclare': 'error',                 // 防止重複宣告
      'no-implicit-globals': 'error',          // 防止隱式全域變數
      'prefer-const': 'error',                 // 強制使用 const
      
      // TypeScript 嚴格規則
      '@typescript-eslint/no-unused-vars': 'error',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-shadow': 'error',
      
      // 命名約定
      '@typescript-eslint/naming-convention': [
        'error',
        // Store 變數應該以 $ 開頭使用
        {
          selector: 'variable',
          format: ['camelCase', 'PascalCase', 'UPPER_CASE'],
          leadingUnderscore: 'allow'
        },
        // 函數命名
        {
          selector: 'function',
          format: ['camelCase', 'PascalCase']
        },
        // 類型命名
        {
          selector: 'typeLike',
          format: ['PascalCase']
        }
      ]
    }
  },
  ...svelte.configs['flat/recommended'],
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
      // Svelte 特定規則
      'svelte/no-dupe-keys': 'error',          // 防止重複鍵
      'svelte/no-unused-svelte-ignore': 'error',
      'svelte/prefer-destructuring-assignment': 'warn'
    }
  }
];