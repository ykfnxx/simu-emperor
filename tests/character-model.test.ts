import { describe, expect, it } from 'vitest';
import {
  buildCharacterTurnPrompt,
  CharacterTextCollector,
  captureCharacterReplyTargets,
  parseCharacterTurnOutput,
} from '../src/officers/character-model-contract.ts';
import { characterInput } from './helpers/character-fixtures.ts';

describe('character model actions', () => {
  it('accepts a greeting report without requests or disclosures', () => {
    const input = characterInput();
    input.replyTargets = [];
    const output = parseCharacterTurnOutput(JSON.stringify({
      submission: { report: { body: '谨向陛下问安。', disclose: [] } },
    }), input);
    expect(output.submission).toEqual({ report: { body: '谨向陛下问安。', disclose: [] } });
    expect(output.submission?.plans).toBeUndefined();
  });

  it('keeps a revised plan explicit and maps only the captured reply target', () => {
    const input = characterInput();
    const output = parseCharacterTurnOutput(JSON.stringify({
      submission: {
        report: { body: '臣已改请银数额。', disclose: ['disposable_silver'] },
        plans: [{ plan_id: 'plan_canal', kind: 'canal', local_amount: 3_000, requested_amount: 2_000, purpose: '续修水渠' }],
      },
      replies: [{ reply_id: 'reply_1', content: '本地出三千两，向朝廷改请两千两。' }],
    }), input);
    expect(output.submission?.plans?.[0]).toMatchObject({ plan_id: 'plan_canal', requested_amount: 2_000 });
    expect(output.replies[0]).toEqual({ reply_id: 'reply_1', output: { content: '本地出三千两，向朝廷改请两千两。' } });
    expect(input.replyTargets[0]?.target).toEqual({ conversation_id: 'conversation_private', wake_id: 7, source_turn: 1 });
    expect(input.brief.assignment.context.turn_number).toBe(2);
  });

  it('withdraws an existing commitment separately and rejects replacing it at the same time', () => {
    const input = characterInput();
    input.reportRequired = false;
    input.replyTargets = [];
    expect(parseCharacterTurnOutput('{"withdraw_plan_ids":["plan_canal"]}', input).withdraw_plan_ids).toEqual(['plan_canal']);
    expect(() => parseCharacterTurnOutput(JSON.stringify({
      withdraw_plan_ids: ['plan_canal'],
      submission: { plans: [{ plan_id: 'plan_canal', kind: 'canal', local_amount: 1, requested_amount: 0, purpose: '修渠' }] },
    }), input)).toThrow('Plan both replaced/withdrawn');
  });

  it('requires a report for the new turn and explicit silence for every wake', () => {
    const input = characterInput();
    expect(() => parseCharacterTurnOutput('{"replies":[]}', input)).toThrow('requires a report');
    input.reportRequired = false;
    expect(() => parseCharacterTurnOutput('{"replies":[{"reply_id":"reply_1","content":""}]}', input)).toThrow('nonempty text');
    expect(() => parseCharacterTurnOutput('{"replies":[{"reply_id":"reply_1","no_reply":true}]}', input)).toThrow('[NO_REPLY]');
    expect(parseCharacterTurnOutput('{"replies":[{"reply_id":"reply_1","no_reply":true,"explicit_directive":"[NO_REPLY]"}]}', input).replies[0]?.output)
      .toEqual({ no_reply: true, explicit_directive: '[NO_REPLY]' });
  });

  it('rejects invalid model shapes and numeric strings rather than coercing them', () => {
    const input = characterInput();
    input.reportRequired = false;
    input.replyTargets = [];
    for (const output of [
      '', '```json\n{}\n```', '{"context":{}}',
      '{"submission":{"report":{"body":"情况","disclose":["population_guess"]}}}',
      '{"submission":{"plans":[{"kind":"relief","local_amount":"1","requested_amount":0,"purpose":"赈济"}]}}',
    ]) {
      expect(() => parseCharacterTurnOutput(output, input)).toThrow();
    }
  });

  it('does not turn announcements or wakes for a previous appointment into required replies', () => {
    const input = characterInput();
    input.inbox.wakes[0]!.target_appointment_id = 'appointment_previous';
    expect(captureCharacterReplyTargets(input.inbox)).toEqual([]);
    const prompt = JSON.parse(buildCharacterTurnPrompt({ ...input, replyTargets: [] }));
    expect(prompt.unread_context[0].messages[0].content).toContain('减少中央请银');
    expect(prompt.required_replies).toEqual([]);
    expect(prompt.private_stance).toContain('保守财政');
    expect(prompt.local_facts).toEqual(input.brief.facts);
    expect(prompt).not.toHaveProperty('hostToken');
  });
});

describe('native final message selection', () => {
  it('keeps final JSON message separate from earlier tool commentary', () => {
    const output = new CharacterTextCollector();
    output.append({ messageId: 'progress', text: '先核对粮情。' });
    output.append({ messageId: 'final', text: '{"replies":' });
    output.append({ messageId: 'final', text: '[]}' });
    expect(output.text).toBe('{"replies":[]}');
  });
  it('leaves an unlabelled malformed output intact for normal validation failure', () => {
    const output = new CharacterTextCollector();
    output.append({ text: '说明' }); output.append({ text: '{}' });
    expect(output.text).toBe('说明{}');
  });
});
