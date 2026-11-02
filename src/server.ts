import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { serve } from '@hono/node-server';
import { createApp, loadLocalEnvFile, resolveAuthConfig } from './app.ts';
import { GameStore } from './engine/game-store.ts';

loadLocalEnvFile();

// Validate required role tokens fail-fast before creating database files or binding sockets.
const authConfig = resolveAuthConfig();

const port = Number(process.env.PORT ?? 8787);
const dbPath = process.env.DATABASE_PATH ?? './data/runtime/simu-emperor.db';

if (dbPath !== ':memory:') {
  mkdirSync(dirname(dbPath), { recursive: true });
}

const store = new GameStore({ dbPath });
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
