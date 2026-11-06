import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRuntimeRegistry } from '@botiverse/oar';
import { scriptedRuntime } from '@botiverse/oar/testing';
import { runCharacterOnce } from '../../src/officers/character-runner.ts';
import { startGame, auth } from './runtime.ts';

const game = await startGame();
try {
  const page = await fetch(game.origin);
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.match(html, /<html/);
  const script = html.match(/src="([^\"]*\/_next\/static\/[^\"]+\.js)"/);
  assert(script, 'Built Next script missing');
  const asset = await fetch(new URL(script[1]!, game.origin));
  assert.equal(asset.status, 200); assert.match(asset.headers.get('content-type')!, /javascript/);
  assert.equal((await fetch(`${game.origin}/api/court/view`)).status, 401);
  const response = await fetch(`${game.origin}/api/court/view`, { headers: { Authorization: `Bearer ${auth.court}` } });
  assert.equal(response.status, 200);
  const view = await response.json();
  assert.equal(view.provinces.length, 15); assert.equal(view.active_turn.turn_number, 1);
  const profile = await fetch(`${game.origin}/api/court/runtime-profile`, {
    method: 'PUT', headers: { Authorization: `Bearer ${auth.court}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: view.game_id, office_id: 'governor_shaanxi', profile: { runtime: 'scripted', model: 'scripted-1', effort: null, mode: 'json' } }),
  });
  assert.equal(profile.status, 200);
  await runCharacterOnce({ characterId: 'character_a', hostToken: auth.host, gameOrigin: game.origin,
    dataDir: join(game.directory, 'characters'), mode: 'once', pollIntervalMs: 1, turnTimeoutMs: 3000, startNewSession: false }, {
    observabilityRootDir: game.directory, codeVersion: 'ci-smoke',
    runtimeRegistry: createRuntimeRegistry([scriptedRuntime({ turn: turn => {
      turn.say(JSON.stringify({ submission: { report: { body: 'CI synthetic report', disclose: [] } }, replies: [] }));
    } })]),
  });
  const cli = fileURLToPath(new URL('../../src/observability/extract-cli.ts', import.meta.url));
  const output = join(game.directory, 'export');
  const result = spawnSync(process.execPath, ['--experimental-strip-types', cli, '--root', game.directory,
    '--character', 'character_a', '--turn', '1', '--out', output], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const exported = JSON.parse(result.stdout);
  assert.equal(exported.invocations.length, 1);
  const timeline = readFileSync(join(output, 'interactions.jsonl'), 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert(timeline.length > 0);
  assert(timeline.every(row => row.invocation_id === exported.invocations[0]));
  for (const args of [[], ['--root', game.directory, '--invocation', 'missing', '--out', join(game.directory, 'missing')]]) {
    const rejected = spawnSync(process.execPath, ['--experimental-strip-types', cli, ...args], { encoding: 'utf8' });
    assert.notEqual(rejected.status, 0);
  }
  console.log('Production Node/Next/HTTP and trace CLI smoke passed');
} finally { await game.stop(); }

const noDebug = await startGame(false, false);
try {
  assert.equal((await fetch(`${noDebug.origin}/api/debug/truth`, { headers: { Authorization: `Bearer ${auth.debug}` } })).status, 403);
  console.log('Disabled debug endpoint rejects even the debug credential');
} finally { await noDebug.stop(); }
