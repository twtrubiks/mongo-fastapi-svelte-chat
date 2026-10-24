import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		port: 5173,
		host: true
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node',
		// 每個測試後還原 vi.spyOn / vi.stubGlobal，避免測試互相污染
		restoreMocks: true,
		unstubGlobals: true
	}
});
