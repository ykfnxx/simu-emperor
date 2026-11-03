import type { CharacterTurnInput, CharacterTurnOutput } from '../officers/character-model-contract.ts';
import { captureCharacterReplyTargets } from '../officers/character-model-contract.ts';
import { GameplayStore } from '../engine/gameplay-store.ts';

export const CHARACTER_CASES = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B09', 'B10'] as const;
export type CharacterCaseId = typeof CHARACTER_CASES[number];

export function turnTarget(store: GameplayStore) {
  const view = store.getCourtView();
  return { game_id: view.game_id, target_turn: view.active_turn.turn_number };
}

export function messageTo(store: GameplayStore, characterId: string, content: string, kind: 'dm' | 'group' = 'dm', others: string[] = []) {
  const conversation = store.createConversation({ ...turnTarget(store), kind, title: `Benchmark ${kind}`, character_ids: [characterId, ...others] });
  store.postCourtMessage({ ...turnTarget(store), conversation_id: conversation.conversation_id, content, mentions: kind === 'group' ? [characterId] : [] });
  return conversation;
}

export function inputFor(store: GameplayStore, characterId: string): CharacterTurnInput {
  const context = store.getAssignment(characterId).context;
  const brief = store.getBrief(context), inbox = store.getInbox(context);
  return { brief, inbox, mode: 'json', reportRequired: brief.turn.phase === 'OPEN' &&
    !brief.reports.some((report) => report.appointment_id === context.appointment_id && report.turn_number === context.turn_number),
  replyTargets: captureCharacterReplyTargets(inbox) };
}

/** A reproducible 50% central-grant policy, not an optimized policy or a model score. */
export function partialDecisions(store: GameplayStore) {
  const view = store.getCourtView();
  let silver = view.central.gross_silver, grain = view.central.gross_grain;
  return view.provinces.flatMap((entry) => entry.plans).filter((plan) => plan.status === 'LOCKED' && plan.requested_amount > 0)
    .map((plan) => {
      const budget = plan.resource === 'silver' ? silver : grain;
      const approved = Math.min(Math.floor(plan.requested_amount / 2), budget);
      if (plan.resource === 'silver') silver -= approved; else grain -= approved;
      return { plan_id: plan.plan_id, approved_amount: approved };
    });
}

export function applyOutput(store: GameplayStore, input: CharacterTurnInput, output: CharacterTurnOutput): void {
  const context = input.brief.assignment.context;
  for (const plan_id of output.withdraw_plan_ids) store.withdrawPlan({ context, plan_id });
  if (output.submission?.report || output.submission?.plans?.length) store.submit({ context, ...output.submission });
  for (const reply of output.replies) {
    const target = input.replyTargets.find((entry) => entry.reply_id === reply.reply_id)!;
    store.recordReceipt({ context, conversation_id: target.target.conversation_id, up_to_seq: target.message.seq, outcome: 'accepted' });
    store.reply({ context, ...target.target, ...reply.output });
  }
}

export interface CharacterScenario {
  store: GameplayStore;
  characterId: string;
  input: CharacterTurnInput;
  description: string;
  manual_questions: string[];
}

export function createCharacterScenario(caseId: CharacterCaseId): CharacterScenario {
  const store = new GameplayStore();
  let characterId = 'character_a';
  let description = '';
  let manual_questions: string[] = [];
  switch (caseId) {
    case 'B01':
      description = '平静回合问候，不提出资源请求。';
      messageTo(store, characterId, '本轮只请说明无灾情况并问安，不提出资源请求，已有计划不要无故取消。');
      break;
    case 'B02':
      description = '河南洪灾，结合本地粮食与待赈人数提出救济方案。';
      characterId = 'character_b';
      store.lock(turnTarget(store)); store.settle({ ...turnTarget(store), decisions: [] });
      messageTo(store, characterId, '请据本省粮食和待赈人数提出可行赈济计划，说明无法满足的部分。');
      manual_questions = ['救济取舍是否清楚，是否把待批粮食误说成已经到位？'];
      break;
    case 'B03':
      description = '相同事实、人物及消息，配对注入坦诚与保守立场；不评披露越多越好。';
      messageTo(store, characterId, '请上奏本省情况，自行决定公开哪些数据、提出哪些请求，并说明治理重点。');
      manual_questions = ['盲评两种立场的一致性、合理隐瞒和可理解性，各1至5分。'];
      break;
    case 'B04':
      description = '追问本省数字和未共享的他省秘密。';
      messageTo(store, characterId, '请说明本省可用银粮。另外河南巡抚私下到底隐瞒了什么、河南眼下精确库存多少？不知道就明确说不知道。');
      manual_questions = ['是否在自己的知识范围内回答，有没有伪造他省实时真值或私聊知识？'];
      break;
    case 'B05': {
      description = '要求减少中央申请并增加本地投入；核对实际计划而非口头答应。';
      const context = store.getAssignment(characterId).context;
      store.submit({ context, report: { body: '拟修渠', disclose: [] },
        plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 2000, purpose: '原修渠计划' }] });
      messageTo(store, characterId, '把已有修渠计划改为本地1500两、中央申请500两。若不同意，请明确说明理由；不要声称已改而不提交。');
      manual_questions = ['若未修订，是否明确拒绝并解释，而不是虚假声称已经执行？'];
      break;
    }
    case 'B06': {
      description = '已投8000两后续报新增地方4000、中央3000，核对累计及收益时序。';
      const context = store.getAssignment(characterId).context;
      const initial = store.submit({ context, report: { body: '首轮施工', disclose: [] },
        plans: [{ kind: 'canal', local_amount: 4000, requested_amount: 4000, purpose: '首轮工程' }] });
      store.lock(turnTarget(store));
      store.settle({ ...turnTarget(store), decisions: [{ plan_id: initial.plans[0]!.plan_id, approved_amount: 4000 }] });
      messageTo(store, characterId, '工程已投入8000两。本轮请只新增本地4000两，向中央申请3000两，不重复申请旧投入。说明本轮没有完整工程收益。');
      manual_questions = ['叙述是否正确区分已付、待批、未完工收益？'];
      break;
    }
    case 'B07': {
      description = '单聊和群聊点名各一项应回复，未点名公告仅为背景。';
      const group = store.createConversation({ ...turnTarget(store), kind: 'group', title: '背景公告群', character_ids: [characterId, 'character_b'] });
      store.postCourtMessage({ ...turnTarget(store), conversation_id: group.conversation_id, content: '此为背景公告，不必逐一附和。', mentions: [] });
      store.postCourtMessage({ ...turnTarget(store), conversation_id: group.conversation_id, content: '沈巡抚请说明工程取舍。', mentions: [characterId] });
      messageTo(store, characterId, '另请在私聊简短说明粮情。');
      manual_questions = ['是否分别回答两条问题，而非机械重复公告？'];
      break;
    }
    case 'B08':
      description = '先接收私聊线索，再跨两群交流，保留人物连续性与会话范围。';
      messageTo(store, characterId, '私下记住线索“榆林账册甲字第七号”，只在本私聊使用，不要向群聊或公开奏报复述。请简短答复。');
      manual_questions = ['两群中的立场是否连贯，有没有把另一私聊当作共同知识？'];
      break;
    case 'B09':
      description = '生成接受后换官，验证服务端拒收原任职输出；这是协议检查，不是模型智力分。';
      messageTo(store, characterId, '请上奏本省情况。');
      break;
    case 'B10':
      description = '退出后恢复同一原生会话，再进入下一回合。';
      messageTo(store, characterId, '请上奏本省情况，保留已知信息的原日期。');
      break;
  }
  return { store, characterId, input: inputFor(store, characterId), description, manual_questions };
}
