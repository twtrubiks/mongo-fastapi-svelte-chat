import { defineConfig, devices } from '@playwright/test';

// 端對端測試：經由 SvelteKit BFF 連到真的 FastAPI、MongoDB 與 Redis。
// 執行前須先啟動後端（見 tests/e2e/README.md）；前端 dev server 若沒在跑會自動啟動
const baseURL = 'http://localhost:5173';

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  // 共用同一個後端，且有等待 10 秒 ack 逾時的測試；依序執行較穩定
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL,
    viewport: { width: 1400, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
