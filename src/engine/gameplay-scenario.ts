import type {
  ActiveProvinceId,
  CharacterPublicView,
  GameplayDisaster,
  OfficeId,
  ProvinceDefinition,
} from '../contracts/gameplay.ts';

export const GAMEPLAY_SCENARIO = {
  id: 'ming-three-provinces-1636',
  start_date: '1636-01-01',
  days_per_turn: 7,
  turns: 4,
  canal_cost_silver: 20_000,
  canal_grain_per_turn: 10_000,
  grain_per_person: 1,
  mandatory_silver: 10_000,
  mandatory_grain: 10_000,
} as const;

export const ACTIVE_PROVINCES: readonly ActiveProvinceId[] = ['shaanxi', 'henan', 'huguang'];

export const MING_PROVINCES: readonly ProvinceDefinition[] = [
  { province_id: 'beizhili', name: '北直隶', active: false, office_id: null },
  { province_id: 'nanzhili', name: '南直隶', active: false, office_id: null },
  { province_id: 'shandong', name: '山东', active: false, office_id: null },
  { province_id: 'shanxi', name: '山西', active: false, office_id: null },
  { province_id: 'henan', name: '河南', active: true, office_id: 'governor_henan' },
  { province_id: 'shaanxi', name: '陕西', active: true, office_id: 'governor_shaanxi' },
  { province_id: 'sichuan', name: '四川', active: false, office_id: null },
  { province_id: 'huguang', name: '湖广', active: true, office_id: 'governor_huguang' },
  { province_id: 'zhejiang', name: '浙江', active: false, office_id: null },
  { province_id: 'jiangxi', name: '江西', active: false, office_id: null },
  { province_id: 'fujian', name: '福建', active: false, office_id: null },
  { province_id: 'guangdong', name: '广东', active: false, office_id: null },
  { province_id: 'guangxi', name: '广西', active: false, office_id: null },
  { province_id: 'yunnan', name: '云南', active: false, office_id: null },
  { province_id: 'guizhou', name: '贵州', active: false, office_id: null },
];

export interface ScenarioCharacter extends CharacterPublicView {
  stance: string;
  initial_office_id: OfficeId | null;
}

// Names and quantities are fictional fixtures for the four-turn trial.
export const SCENARIO_CHARACTERS: readonly ScenarioCharacter[] = [
  {
    character_id: 'character_a', name: '沈安民', biography: '曾任县令，熟悉灾后赈务。',
    specialty: '赈务', stance: '赈民优先，主动说明灾情和赈济缺口。',
    initial_office_id: 'governor_shaanxi',
  },
  {
    character_id: 'character_b', name: '陆慎之', biography: '曾管府库，重视收支平衡。',
    specialty: '财政', stance: '保守财政，谨慎承诺地方投入。',
    initial_office_id: 'governor_henan',
  },
  {
    character_id: 'character_c', name: '顾维功', biography: '曾督修水利，熟悉地方工程。',
    specialty: '水利', stance: '维护自身政绩，可能回避不利细节，但不伪造结构化数字。',
    initial_office_id: 'governor_huguang',
  },
  {
    character_id: 'character_d', name: '陈知远', biography: '曾参与核查地方钱粮，现候任。',
    specialty: '核查', stance: '先核实事实，再说明可行的治理选择。', initial_office_id: null,
  },
];

export interface GameplayProvinceTurn {
  inflow_silver: number;
  inflow_grain: number;
  registered_population: number;
  relief_population: number;
  disaster_type: GameplayDisaster;
  disaster_label: string;
}

export interface GameplayTurnScript {
  central_inflow_silver: number;
  central_inflow_grain: number;
  provinces: Record<ActiveProvinceId, GameplayProvinceTurn>;
}

function province(
  silver: number, grain: number, relief: number,
  disaster_type: GameplayDisaster = 'none', disaster_label = '无灾',
): GameplayProvinceTurn {
  return {
    inflow_silver: silver, inflow_grain: grain, registered_population: 100_000,
    relief_population: relief, disaster_type, disaster_label,
  };
}

export const GAMEPLAY_TURNS: readonly GameplayTurnScript[] = [
  {
    central_inflow_silver: 15_000, central_inflow_grain: 5_000,
    provinces: {
      shaanxi: province(20_000, 10_000, 0),
      henan: province(15_000, 20_000, 0),
      huguang: province(15_000, 20_000, 0),
    },
  },
  {
    central_inflow_silver: 15_000, central_inflow_grain: 5_000,
    provinces: {
      shaanxi: province(10_000, 10_000, 0),
      henan: province(10_000, 10_000, 30_000, 'flood', '洪灾'),
      huguang: province(10_000, 10_000, 20_000, 'drought', '旱灾'),
    },
  },
  {
    central_inflow_silver: 15_000, central_inflow_grain: 10_000,
    provinces: {
      shaanxi: province(10_000, 10_000, 0),
      henan: province(10_000, 10_000, 20_000, 'flood', '余涝'),
      huguang: province(10_000, 10_000, 0),
    },
  },
  {
    central_inflow_silver: 15_000, central_inflow_grain: 10_000,
    provinces: {
      shaanxi: province(10_000, 10_000, 0),
      henan: province(10_000, 10_000, 0),
      huguang: province(10_000, 10_000, 10_000, 'drought', '旱情'),
    },
  },
];

export function gameplayTurnDate(turn: number): string {
  if (!Number.isSafeInteger(turn) || turn < 1 || turn > GAMEPLAY_SCENARIO.turns) {
    throw new RangeError('Invalid trial turn');
  }
  const date = new Date(`${GAMEPLAY_SCENARIO.start_date}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + (turn - 1) * GAMEPLAY_SCENARIO.days_per_turn);
  return date.toISOString().slice(0, 10);
}
