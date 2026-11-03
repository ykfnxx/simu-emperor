import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { relative, join } from 'node:path';
import { tmpdir } from 'node:os';
import { describe, expect, it } from 'vitest';
import { createApp } from '../src/app.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';

const auth = {
  monarchToken: 'entry-test-court', monarchDebugToken: 'entry-test-debug',
  agentHostToken: 'entry-test-host', enableDebugTruth: false,
};

describe('production application composition', () => {
  it('serves the export and Ming API on one origin without reviving old routes', async () => {
    const root = mkdtempSync(join(tmpdir(), 'ming-export-'));
    mkdirSync(join(root, '_next/static'), { recursive: true });
    writeFileSync(join(root, 'index.html'), '<html><body>Ming court</body></html>');
    writeFileSync(join(root, '_next/static/app.js'), 'window.ming = true;');
    const store = new GameplayStore();
    try {
      const app = createApp(store, auth, relative(process.cwd(), root));
      const page = await app.request('/');
      expect(page.status).toBe(200);
      expect(page.headers.get('content-type')).toContain('text/html');
      expect(await page.text()).toContain('Ming court');
      const script = await app.request('/_next/static/app.js');
      expect(script.status).toBe(200);
      expect(script.headers.get('content-type')).toMatch(/javascript/);
      expect(await script.text()).toBe('window.ming = true;');
      const view = await app.request('/api/court/view', { headers: { authorization: `Bearer ${auth.monarchToken}` } });
      expect(view.status).toBe(200);
      const body = await view.json();
      expect(body.provinces).toHaveLength(15);
      expect((await app.request('/api/court/view')).status).toBe(401);
      expect((await app.request('/api/officer/brief', { headers: { authorization: `Bearer ${auth.agentHostToken}` } })).status).toBe(404);
      expect((await app.request('/missing.js')).status).toBe(404);
    } finally {
      store.close();
      rmSync(root, { recursive: true, force: true });
    }
  });
});
