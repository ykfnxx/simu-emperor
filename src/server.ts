import { existsSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { serve } from '@hono/node-server';
import { createApp } from './app.ts';
import { resolveGameplayAuth } from './gameplay-app.ts';
import { GameplayStore } from './engine/gameplay-store.ts';

if (existsSync('.env')) process.loadEnvFile('.env');

// Validate required role tokens fail-fast before creating database files or binding sockets.
const authConfig = resolveGameplayAuth();

const port = Number(process.env.PORT ?? 8787);
const dbPath = process.env.DATABASE_PATH ?? './data/runtime/ming-gameplay.db';

if (dbPath !== ':memory:') {
  mkdirSync(dirname(dbPath), { recursive: true });
}

const store = new GameplayStore({ dbPath });
const app = createApp(store, authConfig);

serve(
  {
    fetch: app.fetch,
    port,
  },
  (info) => {
    console.log(`Simu-Emperor server listening on http://localhost:${info.port}`);
  },
);
