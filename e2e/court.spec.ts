import { test, expect, auth } from './fixtures.ts';
import type { Page, Locator } from '@playwright/test';

async function province(page: Page, id: string) {
  await page.getByTestId(`map-province-${id}`).focus();
  await page.keyboard.press('Enter');
}
async function loopFocus(page: Page, dialog: Locator) {
  await expect(dialog).toBeVisible();
  for (const key of [...Array(18).fill('Tab'), ...Array(18).fill('Shift+Tab')]) {
    await page.keyboard.press(key);
    expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true);
  }
}

test('U01/U23: fresh credentials, invalid token and recovery', async ({ browser, game }) => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage(); await page.goto(game.origin);
    await page.getByLabel('君主凭据', { exact: true }).fill('wrong-token');
    await page.getByRole('button', { name: '存凭据', exact: true }).click();
    await expect(page.getByTestId('auth-recovery-dialog')).toBeVisible();
    await page.getByLabel('君主凭据', { exact: true }).fill(auth.court);
    await page.getByRole('button', { name: '存凭据', exact: true }).click();
    await expect(page.getByTestId('court-shell')).toBeVisible();
    await page.keyboard.press('Escape'); await page.reload();
    await expect(page.getByTestId('court-shell')).toBeVisible();
  } finally { await context.close(); }
});

test('U02/U03/U04/U05/U21/U22: map, layers, panels, events and report archive', async ({ page, view }, info) => {
  const snapshot = await view();
  await expect(page.getByTestId('floating-chat-window')).toBeVisible();
  await page.getByTestId('close-chat-btn').click();
  await expect(page.getByTestId('floating-chat-window')).toBeHidden();
  await page.locator('text.map-state-title').filter({ hasText: /^河南$/ }).click();
  await expect(page.getByTestId('minister-bio-btn')).toBeVisible();
  await page.locator('text.map-state-title').filter({ hasText: /^山东$/ }).click();
  await expect(page.getByTestId('minister-chat-btn')).toHaveCount(0);
  const stage = page.getByTestId('map-camera-stage');
  const before = await stage.getAttribute('data-pan-x');
  await page.mouse.move(800, 600); await page.mouse.down(); await page.mouse.move(870, 630, { steps: 10 }); await page.mouse.up();
  expect(await stage.getAttribute('data-pan-x')).not.toBe(before);
  const zoom = await stage.getAttribute('data-zoom'); await page.mouse.wheel(0, -200);
  await expect(stage).not.toHaveAttribute('data-zoom', zoom!);
  await province(page, 'henan'); await expect(page.getByTestId('map-province-henan')).toHaveAttribute('data-selected', 'true');
  for (const layer of ['silver', 'grain', 'disaster']) {
    await page.getByTestId(`layer-btn-${layer}`).click();
    await expect(page.getByTestId(`layer-btn-${layer}`)).toHaveAttribute('aria-pressed', 'true');
  }
  for (const name of ['太仓钱粮', '户口灾情', '百官']) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.getByTestId('national-panel')).toBeVisible();
    await expect(page.getByTestId('left-context-panel')).toBeVisible();
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.getByTestId('national-panel')).toBeHidden();
  }
  await page.getByTestId('overview-item-henan').click();
  await expect(page.locator('#panel-title')).toContainText('河南');
  await expect(page.getByTestId('overview-item-shandong')).toContainText('银—');
  await expect(page.getByTestId('overview-item-shandong')).toContainText('粮—');
  await page.getByTestId('toggle-overview-btn').click(); await expect(page.locator('#overview-list')).toBeHidden();
  await page.getByTestId('toggle-overview-btn').click(); await expect(page.locator('#overview-list')).toBeVisible();
  await page.getByTestId('overview-item-shaanxi').click();
  await page.getByTestId('event-pill-shaanxi').click();
  await loopFocus(page, page.getByTestId('event-dialog'));
  await page.getByRole('button', { name: '阅奏', exact: true }).click();
  await expect(page.getByText('陕西本轮部分披露', { exact: true })).toBeVisible();
  await page.getByTestId('report-archive-btn').click();
  await loopFocus(page, page.getByTestId('report-archive-dialog'));
  await expect(page.getByTestId('report-archive-dialog')).toContainText('首轮档案 character_a');
  await expect(page.getByTestId('report-archive-dialog')).toContainText('陕西本轮部分披露');
  await page.keyboard.press('Escape');
  expect((await view()).active_turn).toEqual(snapshot.active_turn);
  await page.screenshot({ path: info.outputPath('desktop.png') });
});

test('U06/U07/U08/U09: biography and nested dialog keyboard/pointer dismissal', async ({ page }) => {
  await province(page, 'shaanxi'); const info = page.getByTestId('minister-bio-btn');
  await info.hover(); await expect(page.getByTestId('bio-dialog')).toHaveAttribute('aria-modal', 'false');
  await page.mouse.move(800, 20); await expect(page.getByTestId('bio-dialog')).toBeHidden();
  await info.focus(); await page.keyboard.press('Enter');
  await loopFocus(page, page.getByTestId('bio-dialog'));
  await page.keyboard.press('Escape'); await expect(page.getByTestId('bio-dialog')).toBeHidden(); await expect(info).toBeFocused();
  await page.getByTestId('minister-chat-btn').click();
  await page.getByRole('button', { name: /^验收廷议/ }).click();
  await page.getByTestId('chat-members-btn').click();
  const members = page.getByTestId('group-members-dialog'); await loopFocus(page, members);
  const memberInfo = members.locator('[data-bio-person]').first();
  await memberInfo.click(); await page.keyboard.press('Escape');
  await expect(page.getByTestId('bio-dialog')).toBeHidden(); await expect(members).toBeVisible(); await expect(memberInfo).toBeFocused();
  await page.keyboard.press('Enter'); await page.locator('#close-bio').click();
  await expect(page.getByTestId('bio-dialog')).toBeHidden();
  await page.mouse.move(800, 20); await memberInfo.hover();
  await expect(page.getByTestId('bio-dialog')).toHaveAttribute('aria-modal', 'false');
  await page.mouse.move(800, 20); await expect(page.getByTestId('bio-dialog')).toBeHidden();
  await page.keyboard.press('Escape'); await expect(members).toBeHidden();
  await page.getByTestId('new-group-chat-btn').click(); await loopFocus(page, page.getByTestId('group-create-dialog')); await page.keyboard.press('Escape');
});

test('U10/U11/U12/U25: conversations, drafts, mentions, persistence and refresh', async ({ page, request, game, view }) => {
  await province(page, 'shaanxi'); await page.getByTestId('minister-chat-btn').click();
  const input = page.getByTestId('chat-input');
  await input.fill('私聊落库');
  const sent = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); expect((await sent).status()).toBe(201);
  await expect(page.getByTestId('chat-messages-list')).toContainText('私聊落库'); await expect(input).toBeFocused();
  await input.fill('沈草稿'); await page.getByTestId('chat-contact-character_b').click();
  await expect(input).toHaveValue(''); await input.fill('陆草稿'); await page.getByTestId('chat-contact-character_a').click(); await expect(input).toHaveValue('沈草稿');
  await page.getByRole('button', { name: /^验收廷议/ }).click();
  const chips = page.locator('[data-testid^="mention-chip-"]');
  await expect(chips).toHaveCount(2);
  await expect(page.getByTestId('mention-chip-character_a')).toHaveClass(/active/);
  for (let i = 0; i < await chips.count(); i++) {
    if ((await chips.nth(i).getAttribute('class'))!.split(' ').includes('active')) await chips.nth(i).click();
  }
  await input.fill('无人点名背景');
  const background = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); const body = await (await background).json(); expect(body.message.wake_targets).toEqual([]);
  await expect(input).toBeFocused();
  await page.getByTestId('mention-chip-character_a').click(); await input.fill('只问沈');
  const named = page.waitForResponse(r => r.url().endsWith('/api/court/messages') && r.request().method() === 'POST');
  await page.getByTestId('send-chat-btn').click(); const targeted = await (await named).json(); expect(targeted.message.wake_targets).toEqual(['character_a']);
  const current = await view();
  const extra = await request.post(`${game.origin}/api/court/messages`, { headers: { Authorization: `Bearer ${auth.court}` }, data: {
    game_id: current.game_id, target_turn: current.active_turn.turn_number, conversation_id: body.message.conversation_id, content: '外部新增消息', mentions: [],
  } }); expect(extra.ok()).toBeTruthy();
  await page.getByTestId('chat-refresh-btn').click(); await expect(page.getByTestId('chat-messages-list')).toContainText('外部新增消息');
  await input.focus(); await page.keyboard.press('Escape'); await expect(page.getByTestId('floating-chat-window')).toBeHidden(); await expect(page.getByTestId('minister-chat-btn')).toBeVisible();
});

test('U13/U14/U18/U24: one-request transfer, historical appointments and conflict rollback', async ({ page, view, request, game }) => {
  const before = await view(); const writes: string[] = [];
  page.on('request', r => { if (r.url().endsWith('/api/court/appointments')) writes.push(r.method()); });
  await page.getByRole('button', { name: '百官', exact: true }).click();
  await page.getByTestId('replace-office-governor_shaanxi').click(); await loopFocus(page, page.locator('#candidate-dialog'));
  await page.getByTestId('candidate-row-character_b').click(); await expect(page.locator('#candidate-dialog')).toBeHidden();
  const after = await view();
  expect(writes).toEqual(['POST']);
  expect(after.provinces.find(p => p.province.province_id === 'shaanxi')!.appointment!.character_id).toBe('character_b');
  expect(after.provinces.find(p => p.province.province_id === 'henan')!.appointment).toBeNull();
  for (const id of ['shaanxi', 'henan']) expect(after.provinces.find(p => p.province.province_id === id)!.plans.every(p => p.status === 'WITHDRAWN')).toBe(true);
  expect(after.provinces[0]!.reports).toEqual(before.provinces[0]!.reports);
  await page.getByRole('button', { name: '起居注', exact: true }).click(); await page.getByTestId('history-turn-1').click();
  await page.getByRole('button', { name: '百官', exact: true }).click();
  await expect(page.getByTestId('office-row-governor_shaanxi')).toContainText('沈安民');
  const buttons = page.locator('[data-testid^="replace-office-"]'); for (let i = 0; i < await buttons.count(); i++) await expect(buttons.nth(i)).toBeDisabled();
  await page.getByTestId('phase-action-btn').click();
  await expect(page.getByTestId('replace-office-governor_huguang')).toBeEnabled(); await page.getByTestId('replace-office-governor_huguang').click();
  await request.post(`${game.origin}/api/court/lock`, { headers: { Authorization: `Bearer ${auth.court}` }, data: { game_id: before.game_id, target_turn: 2 } });
  const locked = await view(); const rejected = page.waitForResponse(r => r.url().endsWith('/api/court/appointments'));
  await page.getByTestId('candidate-row-character_d').click(); expect((await rejected).status()).toBe(409);
  expect((await view()).provinces).toEqual(locked.provinces);
});

test('U15/U16/U17/U19: invalid drafts, budget rejection, partial/local funding and ending', async ({ page, view }) => {
  const before = await view();
  const plans = Object.fromEntries(before.provinces.filter(p => p.province.active).map(p => [p.province.province_id, p.plans]));
  async function phase(path: string) {
    const result = page.waitForResponse(r => r.url().endsWith(path) && r.request().method() === 'POST');
    await page.getByTestId('phase-action-btn').click(); expect((await result).status()).toBe(200);
  }
  async function approval(id: string, amount: string) {
    await page.getByTestId(`overview-item-${id}`).click(); await page.getByTestId('province-tab-approval').click();
    const plan = plans[id]!.find(p => p.requested_amount > 0)!;
    await page.getByTestId(`grant-input-${plan.plan_id}`).fill(amount); await page.getByTestId('confirm-approval-btn').click();
  }
  await phase('/api/court/lock');
  await page.getByTestId('overview-item-shaanxi').click(); await page.getByTestId('province-tab-approval').click();
  const input = page.getByTestId(`grant-input-${plans.shaanxi![0]!.plan_id}`);
  for (const value of ['', '-1', '100.5', '5001']) {
    await input.fill(value); if (await page.getByTestId('confirm-approval-btn').isEnabled()) await page.getByTestId('confirm-approval-btn').click();
    await expect(input).toHaveValue(value); await expect(page.getByRole('alert').first()).toBeVisible();
  }
  await page.getByTestId(`grant-max-${plans.shaanxi![0]!.plan_id}`).click(); await expect(input).toHaveValue('5000');
  await page.getByTestId(`grant-zero-${plans.shaanxi![0]!.plan_id}`).click(); await expect(input).toHaveValue('0');
  await approval('shaanxi', '0'); await expect(input).toHaveValue('0');
  await approval('shaanxi', '3000'); await approval('henan', '8000'); await approval('huguang', '5000');
  if (await page.getByTestId('phase-action-btn').isEnabled()) {
    const denied = page.waitForResponse(r => r.url().endsWith('/api/court/settle'));
    await page.getByTestId('phase-action-btn').click(); expect((await denied).status()).toBeGreaterThanOrEqual(400);
  }
  expect((await view()).central).toEqual(before.central); expect((await view()).active_turn.phase).toBe('LOCKED');
  await approval('huguang', '2000');
  const local = plans.huguang!.find(p => p.requested_amount === 0)!;
  await expect(page.getByTestId(`grant-input-${local.plan_id}`)).toHaveCount(0);
  await page.reload(); await page.getByTestId('overview-item-shaanxi').click(); await page.getByTestId('province-tab-approval').click(); await expect(input).toHaveValue('3000'); expect((await view()).central).toEqual(before.central);
  await phase('/api/court/settle');
  expect((await view()).active_turn.turn_number).toBe(3);
  expect((await view()).central).toEqual({ gross_silver: before.central.gross_silver - 3000 + 15000, gross_grain: before.central.gross_grain - 10000 + 10000 });
  expect((await view()).provinces.find(p => p.province.province_id === 'huguang')!.project!.paid_silver).toBe(1000);
  for (const turn of [3, 4]) {
    await expect(page.getByTestId('hud-phase-badge')).toContainText('议政');
    await phase('/api/court/lock'); await expect(page.getByTestId('hud-phase-badge')).toContainText('批复'); await phase('/api/court/settle');
  }
  await expect(page.getByTestId('phase-action-btn')).toHaveText('四轮终局'); await expect(page.getByTestId('phase-action-btn')).toBeDisabled();
  expect((await view()).active_turn.turn_number).toBe(4);
  await expect(page.getByTestId('hud-phase-badge')).toContainText('终局');
});

test('U09/U20: runtime profile persists without changing Pi to another engine', async ({ page, view, request, game }) => {
  const current = await view(); const profile = { runtime: 'pi', model: 'ci-model', effort: 'low', mode: 'json' };
  expect((await request.put(`${game.origin}/api/court/runtime-profile`, { headers: { Authorization: `Bearer ${auth.court}` }, data: { game_id: current.game_id, office_id: 'governor_shaanxi', profile } })).ok()).toBeTruthy();
  await page.reload(); await page.getByRole('button', { name: '机务', exact: true }).click();
  await loopFocus(page, page.getByTestId('settings-dialog'));
  await expect(page.locator('#setting-engine')).toHaveValue('pi'); await expect(page.locator('#setting-model')).toHaveValue('ci-model');
  await expect(page.getByLabel('筹思力度')).toHaveValue('low'); await expect(page.getByLabel('推演模式')).toHaveValue('json');
  await page.getByTestId('save-runtime-profile-btn').click(); await page.keyboard.press('Escape'); await page.reload();
  await page.getByRole('button', { name: '机务', exact: true }).click(); await expect(page.locator('#setting-engine')).toHaveValue('pi');
});

test('Kimi v4: desktop chat remains centered at 4:3 with equal rails', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const [width, height] of [[1280, 800], [1440, 900], [1920, 1080], [3840, 2160]] as const) {
    await page.setViewportSize({ width, height });
    const chat = await page.getByTestId('floating-chat-window').boundingBox();
    const left = await page.getByTestId('left-context-panel').boundingBox();
    const right = await page.getByTestId('right-overview-panel').boundingBox();
    expect(chat).not.toBeNull(); expect(left).not.toBeNull(); expect(right).not.toBeNull();
    expect(chat!.width).toBeLessThanOrEqual(880);
    expect(chat!.width / chat!.height).toBeCloseTo(4 / 3, 2);
    expect(chat!.x + chat!.width / 2).toBeCloseTo(width / 2, 0);
    expect(chat!.y + chat!.height / 2).toBeCloseTo(height / 2, 0);
    expect(left!.height).toBeCloseTo(chat!.height, 0);
    expect(right!.height).toBeCloseTo(chat!.height, 0);
    expect(chat!.x - left!.x - left!.width).toBeGreaterThanOrEqual(15);
    expect(right!.x - chat!.x - chat!.width).toBeGreaterThanOrEqual(15);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  }
});

test('Kimi v4: pinned person card transfers and dismisses with real mouse clicks', async ({ page, view }) => {
  await page.getByTestId('top-btn-talent').click();
  await page.getByTestId('roster-person-character_b').click();
  const card = page.getByTestId('bio-dialog');
  await expect(card).toHaveAttribute('aria-modal', 'true');
  await expect(card.locator('#bio-summary')).toHaveText('曾管府库，重视收支平衡。');
  await page.getByTestId('bio-office-select').selectOption('governor_shaanxi');
  const writes: string[] = [];
  page.on('request', r => { if (r.url().endsWith('/api/court/appointments')) writes.push(r.method()); });
  const [moved] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/court/appointments')),
    page.getByTestId('bio-appoint-submit-btn').click(),
  ]);
  expect(moved.status()).toBe(200); expect(writes).toEqual(['POST']);
  await expect(card.locator('#bio-courtesy')).toContainText('陕西');
  const current = await view();
  expect(current.provinces.find(p => p.province.province_id === 'shaanxi')!.appointment!.character_id).toBe('character_b');
  expect(current.provinces.find(p => p.province.province_id === 'henan')!.appointment).toBeNull();
  const [dismissed] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/court/appointments')),
    page.getByTestId('bio-dismiss-btn').click(),
  ]);
  expect(dismissed.status()).toBe(200); expect(writes).toEqual(['POST', 'POST']);
  await expect(card.locator('#bio-courtesy')).toContainText('候任');
  expect((await view()).provinces.find(p => p.province.province_id === 'shaanxi')!.appointment).toBeNull();
  await page.keyboard.press('Escape');
  await page.getByTestId('top-btn-history').click(); await page.getByTestId('history-turn-1').click();
  await page.getByTestId('top-btn-talent').click(); await page.getByTestId('roster-person-character_b').click();
  await expect(page.getByTestId('hud-phase-badge')).toContainText('归档');
  await expect(page.getByTestId('hud-phase-badge')).not.toContainText('终局');
  await expect(card.locator('#bio-courtesy')).toContainText('河南');
  await expect(page.getByTestId('bio-timeline').locator('[data-testid^="bio-history-"]')).toHaveCount(1);
  await expect(page.getByTestId('bio-appoint-submit-btn')).toBeDisabled();
  await expect(page.getByTestId('bio-dismiss-btn')).toBeDisabled();
});

test('Kimi v4: event and province share approval drafts without early payment', async ({ page, view }) => {
  const before = await view();
  const plan = before.provinces.find(p => p.province.province_id === 'henan')!.plans.find(p => p.requested_amount > 0)!;
  const [locked] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/court/lock')),
    page.getByTestId('phase-action-btn').click(),
  ]);
  expect(locked.status()).toBe(200);
  await page.getByTestId('overview-item-henan').click(); await page.getByTestId('event-pill-henan').click();
  const input = page.getByTestId(`event-grant-input-${plan.plan_id}`);
  await input.fill('-1'); await input.blur();
  await expect(input).toHaveValue('-1'); await expect(page.getByRole('alert').first()).toBeVisible();
  await input.fill('1500'); await input.blur(); await page.keyboard.press('Escape');
  await page.getByTestId('province-tab-approval').click();
  await expect(page.getByTestId(`grant-input-${plan.plan_id}`)).toHaveValue('1500');
  await page.reload(); await page.getByTestId('overview-item-henan').click(); await page.getByTestId('province-tab-approval').click();
  await expect(page.getByTestId(`grant-input-${plan.plan_id}`)).toHaveValue('1500');
  const drafted = await view(); expect(drafted.central).toEqual(before.central); expect(drafted.active_turn.phase).toBe('LOCKED');
});
