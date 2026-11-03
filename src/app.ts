import { serveStatic } from '@hono/node-server/serve-static';
import { createGameplayApp, type GameplayAuthOptions } from './gameplay-app.ts';
import type { GameplayStore } from './engine/gameplay-store.ts';

export function createApp(
  store: GameplayStore,
  auth: GameplayAuthOptions = {},
  staticRoot = './out',
) {
  const app = createGameplayApp(store, auth);
  app.get('*', serveStatic({ root: staticRoot }));
  return app;
}
