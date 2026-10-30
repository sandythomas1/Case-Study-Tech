import js from '@eslint/js';
import ts from 'typescript-eslint';

export default ts.config(
  { ignores: ['node_modules/**', 'dist/**', '.expo/**', 'coverage/**', 'android/**', 'ios/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { languageOptions: { globals: { describe: 'readonly', it: 'readonly', expect: 'readonly', __dirname: 'readonly', module: 'readonly' } } },
);
