import {
  type ConversationKind,
  type ActorId,
  type DisasterType,
  type LegendItemView,
  type StateId,
  WAN,
} from '../contracts/index.ts';

export interface ScriptedStateWeekConfig {
  inflow_silver: number;
  inflow_grain: number;
  disaster_type: DisasterType;
  disaster_label: string;
  relief_demand_grain: number;
}

export interface ScriptedWeekConfig {
  week_number: 1 | 2 | 3 | 4;
  central_inflow_silver: number;
  central_inflow_grain: number;
  states: Record<StateId, ScriptedStateWeekConfig>;
}

export const MAP_LEGEND_ITEMS: readonly LegendItemView[] = [
  { key: 'urgent', label: '[红] 告急' },
  { key: 'mild', label: '[橙] 轻灾' },
  { key: 'stable', label: '[绿] 安定' },
  { key: 'unknown', label: '[斜纹深灰] 本周未奏报（未知）' },
  { key: 'background', label: '[浅灰] 地理背景区（未启用）' },
] as const;

export const TRIAL_SCRIPT: Record<1 | 2 | 3 | 4, ScriptedWeekConfig> = {
  1: {
    week_number: 1,
    central_inflow_silver: 15_000, // 1.5万两
    central_inflow_grain: 5_000, // 0.5万石
    states: {
      state_a: {
        inflow_silver: 20_000, // 2.0万两 (1.0万 disposable after mandatory)
        inflow_grain: 10_000, // 1.0万石 (0 disposable after mandatory)
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_b: {
        inflow_silver: 15_000, // 1.5万两 (0.5万 disposable)
        inflow_grain: 20_000, // 2.0万石 (1.0万 disposable)
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_c: {
        inflow_silver: 15_000, // 1.5万两 (0.5万 disposable)
        inflow_grain: 20_000, // 2.0万石 (1.0万 disposable)
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
    },
  },
  2: {
    week_number: 2,
    central_inflow_silver: 15_000, // +1.5万两 -> 3.0万两 when Week 1 settles with 0 central spend
    central_inflow_grain: 5_000, // +0.5万石 -> 1.0万石 when Week 1 settles with 0 central spend
    states: {
      state_a: {
        inflow_silver: 10_000, // +1.0万两 -> 2.0万两 gross in Week 2
        inflow_grain: 10_000, // +1.0万石 -> 1.0万石 gross in Week 2
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_b: {
        inflow_silver: 10_000, // +1.0万两 -> 1.5万两 gross in Week 2
        inflow_grain: 10_000, // +1.0万石 -> 2.0万石 gross in Week 2
        disaster_type: 'flood',
        disaster_label: '洪灾',
        relief_demand_grain: 3 * WAN, // 3.0万石
      },
      state_c: {
        inflow_silver: 10_000, // +1.0万两 -> 1.5万两 gross in Week 2
        inflow_grain: 10_000, // +1.0万石 -> 2.0万石 gross in Week 2
        disaster_type: 'drought',
        disaster_label: '旱灾',
        relief_demand_grain: 2 * WAN, // 2.0万石
      },
    },
  },
  3: {
    week_number: 3,
    central_inflow_silver: 15_000, // +1.5万两
    central_inflow_grain: 10_000, // +1.0万石
    states: {
      state_a: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_b: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'flood',
        disaster_label: '余涝',
        relief_demand_grain: 2 * WAN, // 2.0万石
      },
      state_c: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
    },
  },
  4: {
    week_number: 4,
    central_inflow_silver: 15_000,
    central_inflow_grain: 10_000,
    states: {
      state_a: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_b: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'none',
        disaster_label: '无灾',
        relief_demand_grain: 0,
      },
      state_c: {
        inflow_silver: 10_000,
        inflow_grain: 10_000,
        disaster_type: 'drought',
        disaster_label: '旱情',
        relief_demand_grain: 1 * WAN, // 1.0万石
      },
    },
  },
};

// Canonical Week 2 initial truth balances from design Section 8.1.
export const CANONICAL_WEEK2_INITIAL_TRUTH = {
  central: {
    gross_silver: 3 * WAN, // 3.0万两
    gross_grain: 1 * WAN, // 1.0万石
  },
  states: {
    state_a: {
      gross_silver: 2 * WAN, // 2.0万两 (disposable 1.0万两)
      gross_grain: 1 * WAN, // 1.0万石 (disposable 0)
      disaster_type: 'none' as DisasterType,
      disaster_label: '无灾',
      relief_demand_grain: 0,
      canal_built: false,
    },
    state_b: {
      gross_silver: 15_000, // 1.5万两 (disposable 0.5万两)
      gross_grain: 2 * WAN, // 2.0万石 (disposable 1.0万石)
      disaster_type: 'flood' as DisasterType,
      disaster_label: '洪灾',
      relief_demand_grain: 3 * WAN, // 3.0万石
      canal_built: false,
    },
    state_c: {
      gross_silver: 15_000, // 1.5万两 (disposable 0.5万两)
      gross_grain: 2 * WAN, // 2.0万石 (disposable 1.0万石)
      disaster_type: 'drought' as DisasterType,
      disaster_label: '旱灾',
      relief_demand_grain: 2 * WAN, // 2.0万石
      canal_built: false,
    },
  },
} as const;

export interface SeedConversationDef {
  conversation_id: string;
  title: string;
  kind: ConversationKind;
  state_id: StateId | null;
  participants: readonly ActorId[];
}

export const SEED_CONVERSATIONS: readonly SeedConversationDef[] = [
  {
    conversation_id: 'conv_state_a',
    title: '甲州单聊',
    kind: 'monarch_dm',
    state_id: 'state_a',
    participants: ['monarch', 'officer_a'],
  },
  {
    conversation_id: 'conv_state_b',
    title: '乙州单聊',
    kind: 'monarch_dm',
    state_id: 'state_b',
    participants: ['monarch', 'officer_b'],
  },
  {
    conversation_id: 'conv_state_c',
    title: '丙州单聊',
    kind: 'monarch_dm',
    state_id: 'state_c',
    participants: ['monarch', 'officer_c'],
  },
  {
    conversation_id: 'conv_court_group',
    title: '朝议群聊',
    kind: 'court_group',
    state_id: null,
    participants: ['monarch', 'officer_a', 'officer_b', 'officer_c'],
  },
  {
    conversation_id: 'conv_peer_a_b',
    title: '甲—乙同僚私聊',
    kind: 'officer_peer',
    state_id: null,
    participants: ['officer_a', 'officer_b'],
  },
  {
    conversation_id: 'conv_peer_a_c',
    title: '甲—丙同僚私聊',
    kind: 'officer_peer',
    state_id: null,
    participants: ['officer_a', 'officer_c'],
  },
  {
    conversation_id: 'conv_peer_b_c',
    title: '乙—丙同僚私聊',
    kind: 'officer_peer',
    state_id: null,
    participants: ['officer_b', 'officer_c'],
  },
] as const;
