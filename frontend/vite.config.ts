import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		// 測試用不到樣式；元件測試時 Tailwind 會在預處理元件的 <style> 時報錯
		...(process.env['VITEST'] ? [] : [tailwindcss()]),
		sveltekit()
	],
	server: {
		port: 5173,
		host: true
	},
	test: {
		// 每個測試後還原 vi.spyOn / vi.stubGlobal，避免測試互相污染
		restoreMocks: true,
		unstubGlobals: true,
		projects: [
			{
				extends: true,
				test: {
					name: 'server',
					include: ['src/**/*.test.ts'],
					exclude: ['src/**/*.svelte.test.ts'],
					environment: 'node'
				}
			},
			{
				// 元件測試（*.svelte.test.ts）：在 jsdom 中以 Svelte 的瀏覽器版本 render
				extends: true,
				plugins: [svelteTesting()],
				test: {
					name: 'client',
					include: ['src/**/*.svelte.test.ts'],
					environment: 'jsdom',
					setupFiles: ['src/tests/setup-client.ts']
				}
			}
		]
	}
});
