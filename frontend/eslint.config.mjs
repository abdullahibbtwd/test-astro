import tseslint from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';
export default tseslint.config(
 {ignores:['node_modules/**','artifacts/**','contracts/**','src/api/schema.d.ts','src/api/zod/**']},
 ...tseslint.configs.recommended,
 {files:['**/*.{ts,tsx}'],plugins:{'react-hooks':hooks},rules:{'@typescript-eslint/no-explicit-any':'off','@typescript-eslint/no-require-imports':'off','@typescript-eslint/no-unused-vars':['error',{argsIgnorePattern:'^_',varsIgnorePattern:'^_',ignoreRestSiblings:true}],'react-hooks/rules-of-hooks':'error','react-hooks/exhaustive-deps':'error'}}
);
