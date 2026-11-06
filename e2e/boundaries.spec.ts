import { test, expect, auth } from './fixtures.ts';

test('U24: API dismissal followed by UI appointment to a vacant office', async ({ page, request, game, view }) => {
  const before = await view();
  const dismissed = await request.post(`${game.origin}/api/court/appointments`, {
    headers: { Authorization: `Bearer ${auth.court}` }, data: {
      game_id: before.game_id, target_turn: 2, office_id: 'governor_shaanxi', character_id: null,
    },
  });
  expect(dismissed.status()).toBe(200);
  const vacant = (await view()).provinces.find(p => p.province.province_id === 'shaanxi')!;
  expect(vacant.appointment).toBeNull(); expect(vacant.plans.every(p => p.status === 'WITHDRAWN')).toBe(true);
  expect(vacant.reports).toEqual(before.provinces.find(p => p.province.province_id === 'shaanxi')!.reports);
  await page.reload(); await page.getByTestId('event-pill-shaanxi').click();
  await expect(page.getByRole('button', { name: '召询', exact: true })).toBeDisabled(); await page.keyboard.press('Escape');
  await page.getByTestId('top-btn-talent').click();
  await expect(page.getByTestId('office-row-governor_shaanxi')).toContainText('悬缺');
  await page.getByTestId('replace-office-governor_shaanxi').click(); await page.getByTestId('candidate-row-character_d').click();
  await expect(page.locator('#candidate-dialog')).toBeHidden();
  expect((await view()).provinces.find(p => p.province.province_id === 'shaanxi')!.appointment!.character_id).toBe('character_d');
  await expect(page.getByTestId('overview-item-shaanxi')).not.toContainText('悬缺');
});

test('U11: create group through the desktop dialog', async ({ page, request, game }) => {
  await page.getByTestId('minister-chat-btn').click(); await page.getByTestId('new-group-chat-btn').click();
  await page.locator('#group-topic-input').fill('新建验收群');
  const created = page.waitForResponse(r => r.url().endsWith('/api/court/conversations') && r.request().method() === 'POST');
  await page.locator('#create-group-btn').click(); expect((await created).status()).toBe(201);
  const { conversations } = await (await request.get(`${game.origin}/api/court/conversations`, { headers: { Authorization: `Bearer ${auth.court}` } })).json();
  expect(conversations.filter((c: { title: string }) => c.title === '新建验收群')).toHaveLength(1);
  await expect(page.getByTestId('chat-messages-list')).not.toContainText('私聊落库');
});

test('U25: real unauthorized send preserves editable text and accepts one retry', async ({ page, request, game }) => {
  await page.getByTestId('minister-chat-btn').click(); const input = page.getByTestId('chat-input');
  await input.fill('拒收后再发送');
  await page.evaluate(() => localStorage.setItem('simu-ming-monarch-settings:v1', JSON.stringify({ courtToken: '', debugToken: '' })));
  const denied = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); expect((await denied).status()).toBe(401);
  await expect(input).toHaveValue('拒收后再发送');
  await expect(page.getByRole('alert').first()).toBeVisible();
  await page.evaluate(token => localStorage.setItem('simu-ming-monarch-settings:v1', JSON.stringify({ courtToken: token, debugToken: '' })), auth.court);
  await page.keyboard.press('Escape');
  const sent = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); const response = await sent; expect(response.status()).toBe(201);
  const { message } = await response.json();
  const { messages } = await (await request.get(`${game.origin}/api/conversations/${message.conversation_id}/messages`, { headers: { Authorization: `Bearer ${auth.court}` } })).json();
  expect(messages.filter((m: { content: string }) => m.content === '拒收后再发送')).toHaveLength(1);
});

test('U23: debug truth requires the debug credential and disappears when disabled', async ({ page }) => {
  await page.getByTestId('top-btn-settings').click(); await page.locator('#setting-debug-token').fill('invalid-debug');
  await page.getByLabel('真值校核').check(); await page.getByTestId('save-settings-btn').click(); await page.keyboard.press('Escape');
  await expect(page.getByTestId('map-debug-truth-shaanxi')).toHaveCount(0);
  await page.getByTestId('top-btn-settings').click(); await page.locator('#setting-debug-token').fill(auth.debug);
  const truth = page.waitForResponse(r => r.url().includes('/api/debug/truth'));
  await page.getByTestId('save-settings-btn').click(); expect((await truth).status()).toBe(200); await page.keyboard.press('Escape');
  await expect(page.getByTestId('map-debug-truth-shaanxi')).toBeVisible();
  await page.getByTestId('top-btn-settings').click(); await page.getByLabel('真值校核').uncheck(); await page.keyboard.press('Escape');
  await expect(page.getByTestId('map-debug-truth-shaanxi')).toHaveCount(0);
});

test('U08: explicit biography close suppresses hover at an overlapping anchor', async ({ page }) => {
  await page.getByTestId('minister-chat-btn').click(); await page.getByRole('button', { name: /^验收廷议/ }).click();
  await page.getByTestId('chat-members-btn').click();
  const anchor = page.getByTestId('group-members-dialog').locator('[data-bio-person]').first();
  await anchor.click(); const close = page.locator('#close-bio'); const box = await close.boundingBox();
  expect(box).not.toBeNull();
  // Controlled geometry exercises the pointer boundary without changing product CSS.
  await anchor.evaluate((element, bounds) => {
    Object.assign((element as HTMLElement).style, { position: 'fixed', left: `${bounds.x}px`, top: `${bounds.y}px`, width: `${bounds.width}px`, height: `${bounds.height}px`, zIndex: '1' });
  }, box!);
  await close.click(); await expect(page.getByTestId('bio-dialog')).toBeHidden();
  await page.mouse.move(800, 20); await anchor.hover();
  await expect(page.getByTestId('bio-dialog')).toHaveAttribute('aria-modal', 'false');
  await anchor.click(); await expect(page.getByTestId('bio-dialog')).toHaveAttribute('aria-modal', 'true');
});

test('U25: stale-turn send is rejected and refreshed conversation remains usable', async ({ page, request, game, view }) => {
  await page.getByTestId('minister-chat-btn').click(); const input = page.getByTestId('chat-input');
  await input.fill('旧轮消息'); const current = await view();
  const headers = { Authorization: `Bearer ${auth.court}` };
  expect((await request.post(`${game.origin}/api/court/lock`, { headers, data: { game_id: current.game_id, target_turn: 2 } })).ok()).toBeTruthy();
  const decisions = current.provinces.flatMap(p => p.plans.filter(plan => plan.requested_amount > 0).map(plan => ({ plan_id: plan.plan_id, approved_amount: 0 })));
  expect((await request.post(`${game.origin}/api/court/settle`, { headers, data: { game_id: current.game_id, target_turn: 2, decisions } })).ok()).toBeTruthy();
  const denied = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); expect((await denied).status()).toBe(409);
  await expect(page.getByRole('alert').first()).toBeVisible();
  await expect(page.getByTestId('chat-messages-list')).not.toContainText('旧轮消息');
  await input.fill('新轮重发');
  const sent = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); expect((await sent).status()).toBe(201);
  await expect(page.getByTestId('chat-messages-list')).toContainText('新轮重发');
});
