import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		host: true,
		proxy: {
			// 其他 API 請求代理到後端（但排除 BFF 路由）
			'^/api/(?!(auth|dashboard|files|test|rooms|notifications|messages/search|invitations)).*': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				secure: false
			},
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true,
				changeOrigin: true
			}
		}
	},
	css: {
		postcss: './postcss.config.js'
	}
});
