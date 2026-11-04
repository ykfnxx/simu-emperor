import { parseArgs } from 'node:util';
import { extractTrace } from './extract.ts';

const { values } = parseArgs({ options: {
  root: { type: 'string', default: process.cwd() },
  out: { type: 'string' },
  invocation: { type: 'string' },
  character: { type: 'string' },
  turn: { type: 'string' },
} });
if (!values.out) throw new Error('Usage: npm run trace:extract -- --out DIR (--invocation ID | --character ID --turn N) [--root DIR]');
const result = extractTrace(values.root, values.out, {
  invocationId: values.invocation, characterId: values.character,
  turn: values.turn === undefined ? undefined : Number(values.turn),
});
console.log(JSON.stringify({ output: values.out, invocations: result.invocation_ids, warnings: result.warnings }));
