import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: vitePreprocess(),
	
	// 僅壓制已知誤報，a11y 警告保持開啟以確保可及性品質
	onwarn: (warning, handler) => {
		// 忽略未使用的 CSS 選擇器警告（Tailwind 動態類別產生的誤報）
		if (warning.code === 'css_unused_selector') return;

		// 其他警告正常處理
		handler(warning);
	},

	kit: {
		// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
		// If your environment is not supported, or you settled on a specific environment, switch out the adapter.
		// See https://svelte.dev/docs/kit/adapters for more information about adapters.
		adapter: adapter(),
		csrf: {
			trustedOrigins: ['*']
		},
		csp: {
			directives: {
				'style-src': ['self', 'unsafe-inline']
			}
		}
	}
};

export default config;
