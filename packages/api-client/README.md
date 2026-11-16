# Typed frontend client

`schema.d.ts` is generated from `docs/openapi.json` using openapi-typescript 7.10.1.
`client.ts` is a small typed fetch wrapper with no runtime dependencies.

```ts
import { createBackcastClient } from '../../packages/api-client/client';
const api = createBackcastClient('/api/v1');
const page = await api.authors({domain:'消费科技', limit:20});
const report = await api.report('kuo');
const job = await api.verify('vision');
// Poll api.job(job.id), stop at succeeded / failed.
```

Regenerate after changing API models:

```sh
python scripts/export_contract.py
npx --yes openapi-typescript@7.10.1 docs/openapi.json --output packages/api-client/schema.d.ts
```

`accuracy` and probability fields use ratios, not percentages. Null means unavailable.
Frontend implementations may copy this folder into their own workspace. Backend-only review tokens are intentionally not part of the client.
