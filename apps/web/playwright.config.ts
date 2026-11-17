import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir:'./tests', timeout:30000, retries:0, workers:1,
  use:{baseURL:'http://127.0.0.1:3001',trace:'retain-on-failure',screenshot:'only-on-failure'},
  webServer:[
    {command:'python scripts/e2e-api.py',cwd:'../..',url:'http://127.0.0.1:8001/api/health',timeout:30000,env:{OPENAI_API_KEY:'',SEARCH_API_KEY:'',REVIEW_API_TOKEN:'e2e-review-token',RESEARCH_WORKER_TOKEN:'e2e-worker-token',ZHIHU_ACCESS_SECRET:'',ZHIHU_CREDENTIAL_FILE:'docs/e2e-no-credentials.env'}},
    {command:'node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3001',url:'http://127.0.0.1:3001',timeout:120000,env:{API_BASE_URL:'http://127.0.0.1:8001',NEXT_DIST_DIR:'.next-e2e',NEXT_TELEMETRY_DISABLED:'1'}}
  ],
  projects:[{name:'chromium',use:{...devices['Desktop Chrome'],channel:'chrome'}}],
});
