/**
 * 与后端 Pydantic 模型对齐的类型定义
 */

// ── 枚举类型 ──

export type Phase = 'RESOLUTION' | 'SUMMARY' | 'INTERACTION' | 'EXECUTION';

export type CropType = 'rice' | 'wheat' | 'millet' | 'tea' | 'silk_mulberry';

// ── 基础数据模型 ──

export interface PopulationData {
  total: number;
  growth_rate: number;
  labor_ratio: number;
  happiness: number;
}

export interface CropData {
  crop_type: CropType;
  area_mu: number;
  yield_per_mu: number;
}

export interface AgricultureData {
  crops: CropData[];
  irrigation_level: number;
}

export interface CommerceData {
  merchant_households: number;
  market_prosperity: number;
}

export interface TradeData {
  trade_volume: number;
  trade_route_quality: number;
}

export interface MilitaryData {
  garrison_size: number;
  equipment_level: number;
  morale: number;
  upkeep_per_soldier: number;
  upkeep: number;
}

export interface TaxationData {
  land_tax_rate: number;
  commercial_tax_rate: number;
  tariff_rate: number;
}

export interface ConsumptionData {
  civilian_grain_per_capita: number;
  military_grain_per_soldier: number;
}

export interface AdministrationData {
  official_count: number;
  official_salary: number;
  infrastructure_maintenance_rate: number;
  infrastructure_value: number;
  court_levy_amount: number;
}

export interface ProvinceBaseData {
  province_id: string;
  name: string;
  population: PopulationData;
  agriculture: AgricultureData;
  commerce: CommerceData;
  trade: TradeData;
  military: MilitaryData;
  taxation: TaxationData;
  consumption: ConsumptionData;
  administration: AdministrationData;
  granary_stock: number;
  local_treasury: number;
}

export interface NationalBaseData {
  turn: number;
  imperial_treasury: number;
  national_tax_modifier: number;
  tribute_rate: number;
  provinces: ProvinceBaseData[];
}

// ── API 响应类型 ──

export interface StateResponse {
  game_id: string;
  current_turn: number;
  phase: Phase;
  provinces: ProvinceBaseData[];
  imperial_treasury: string;
  active_events_count: number;
}

export interface ChatResponse {
  agent_id: string;
  response: string;
}

export interface ReportResponse {
  agent_id: string;
  turn: number;
  markdown: string;
}

export interface AdvanceResponse {
  phase: Phase;
  turn: number;
  message: string;
  reports: Record<string, string> | null;
  events: GameEvent[] | null;
}

export interface CommandResponse {
  status: string;
  command_type: string;
  direct: boolean;
}

export interface ErrorResponse {
  error: string;
  detail: string | null;
}

// ── Agent 相关 ──

export interface Agent {
  id: string;
  name: string;
  title: string;
  avatar_url?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

// ── 事件相关 ──

export interface GameEvent {
  event_id: string;
  source: 'player' | 'agent' | 'random';
  target_path: string;
  operation: 'add' | 'multiply' | 'set';
  value: number;
  description: string;
}

// ── 回合指标 ──

export interface ProvinceTurnMetrics {
  province_id: string;
  food_production: number;
  food_consumption: number;
  food_balance: number;
  land_tax_revenue: number;
  commercial_tax_revenue: number;
  tariff_revenue: number;
  total_tax_revenue: number;
  military_upkeep: number;
  admin_cost: number;
  net_income: number;
  population_change: number;
  happiness_change: number;
  morale_change: number;
  commerce_change: number;
}

export interface NationalTurnMetrics {
  total_food_production: number;
  total_food_consumption: number;
  total_food_balance: number;
  total_land_tax: number;
  total_commercial_tax: number;
  total_tariff: number;
  total_revenue: number;
  total_military_upkeep: number;
  total_admin_cost: number;
  net_national_income: number;
  tribute_collected: number;
}
