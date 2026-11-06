import { test as base, expect } from '@playwright/test';
import { startGame, auth } from '../scripts/ci/runtime.ts';
import type { GameplayCourtView } from '../src/contracts/gameplay.ts';

export const test = base.extend<{ game: Awaited<ReturnType<typeof startGame>>; view: () => Promise<GameplayCourtView> }>({
  game: async ({}, use, info) => {
    const game = await startGame(true);
    try { await use(game); }
    finally {
      if (info.status !== info.expectedStatus) await info.attach('server.log', { body: game.output(), contentType: 'text/plain' });
      await game.stop();
    }
  },
  view: async ({ game, request }, use) => {
    await use(async () => {
      const response = await request.get(`${game.origin}/api/court/view`, { headers: { Authorization: `Bearer ${auth.court}` } });
      expect(response.ok()).toBeTruthy(); return response.json();
    });
  },
  page: async ({ page, game }, use, info) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(token => {
      if (!localStorage.getItem('simu-ming-monarch-settings:v1')) localStorage.setItem('simu-ming-monarch-settings:v1', JSON.stringify({ courtToken: token, debugToken: '' }));
    }, auth.court);
    await page.goto(game.origin);
    await expect(page.getByTestId('court-shell')).toBeVisible();
    await use(page);
    if (info.status === info.expectedStatus) expect(errors).toEqual([]);
  },
});
export { expect, auth };
