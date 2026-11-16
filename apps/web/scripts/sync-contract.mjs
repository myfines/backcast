// Copies the backend-owned TypeScript contract into apps/web so the web image
// (Docker context = apps/web) builds without reaching outside its folder.
// Run after the backend updates docs/openapi.json + packages/api-client.
import { copyFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const from = resolve(here, '../../../packages/api-client/schema.d.ts');
const to = resolve(here, '../lib/contract/schema.d.ts');
copyFileSync(from, to);
console.log(`synced ${from} -> ${to}`);
