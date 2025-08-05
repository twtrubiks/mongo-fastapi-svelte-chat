import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: vitePreprocess(),
	
	// 忽略開發階段不重要的警告
	onwarn: (warning, handler) => {
		// 忽略所有無障礙性相關警告
		if (warning.code?.startsWith('a11y')) return;
		
		// 忽略未使用的 CSS 選擇器警告 (注意是下劃線)
		if (warning.code === 'css_unused_selector') return;
		
		// 忽略非響應式更新警告
		if (warning.code === 'non_reactive_update') return;
		
		// 其他警告正常處理
		handler(warning);
	},

	kit: {
		// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
		// If your environment is not supported, or you settled on a specific environment, switch out the adapter.
		// See https://svelte.dev/docs/kit/adapters for more information about adapters.
		adapter: adapter(),
		csrf: {
			checkOrigin: false
		},
		csp: {
			directives: {
				'style-src': ['self', 'unsafe-inline']
			}
		}
	}
};

export default config;
