import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { GameplayStore } from '../../src/engine/gameplay-store.ts';

export const auth = { court: 'ci-court-token', debug: 'ci-debug-token', host: 'ci-host-token' };
const repo = fileURLToPath(new URL('../../', import.meta.url));

export async function startGame(seeded = false, debugTruth = true) {
  const directory = mkdtempSync(join(tmpdir(), 'simu-ci-'));
  const dbPath = join(directory, 'game.db');
  symlinkSync(join(repo, 'out'), join(directory, 'out'), 'dir');
  const store = new GameplayStore({ dbPath, logger: () => {} });
  try {
    if (seeded) {
      const target = () => ({ game_id: store.getCourtView().game_id, target_turn: store.getCourtView().active_turn.turn_number });
      for (const id of ['character_a', 'character_b', 'character_c']) {
        store.submit({ context: store.getAssignment(id).context, report: { body: `首轮档案 ${id}`, disclose: ['gross_silver'] } });
      }
      store.lock(target()); store.settle({ ...target(), decisions: [] });
      store.submit({ context: store.getAssignment('character_a').context,
        report: { body: '陕西本轮部分披露', disclose: ['gross_silver', 'gross_grain'] },
        plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 5000, purpose: '陕西修渠' }] });
      store.submit({ context: store.getAssignment('character_b').context,
        report: { body: '河南本轮灾情', disclose: ['gross_grain', 'disaster_type', 'relief_population'] },
        plans: [{ kind: 'relief', local_amount: 1000, requested_amount: 10000, purpose: '河南赈济' }] });
      store.submit({ context: store.getAssignment('character_c').context,
        plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 0, purpose: '地方独资' },
          { kind: 'relief', local_amount: 0, requested_amount: 8000, purpose: '湖广请粮' }] });
      store.createConversation({ ...target(), kind: 'group', title: '验收廷议', character_ids: ['character_a', 'character_b'] });
    }
  } finally { store.close(); }
  const child = spawn(process.execPath, ['--experimental-strip-types', join(repo, 'src/server.ts')], {
    cwd: directory, env: { ...process.env, PORT: '0', DATABASE_PATH: dbPath, MONARCH_TOKEN: auth.court,
      MONARCH_DEBUG_TOKEN: auth.debug, AGENT_HOST_TOKEN: auth.host, ENABLE_DEBUG_TRUTH: debugTruth ? '1' : '0', CODE_VERSION: process.env.GITHUB_SHA ?? 'local-ci' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  async function stop() {
    if (child.exitCode === null && child.signalCode === null) {
      const exited = once(child, 'exit'); child.kill('SIGTERM'); await exited;
    }
    rmSync(directory, { recursive: true, force: true });
  }
  try {
    const origin = await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Server readiness timeout\n${output}`)), 15_000);
      const onData = () => {
        const match = output.match(/listening on http:\/\/localhost:(\d+)/);
        if (match) { clearTimeout(timer); child.stdout.off('data', onData); resolve(`http://127.0.0.1:${match[1]}`); }
      };
      child.stdout.on('data', onData);
      child.once('error', error => { clearTimeout(timer); reject(error); });
      child.once('exit', code => { clearTimeout(timer); reject(new Error(`Server exited ${code}\n${output}`)); });
    });
    return { origin, directory, stop, output: () => output };
  } catch (error) { await stop(); throw error; }
}
