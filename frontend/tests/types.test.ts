import { describe, it, expect } from 'vitest'
import type {
  Phase,
  ProvinceBaseData,
  NationalBaseData,
  StateResponse,
  Agent,
  ChatMessage,
  AdvanceResponse,
} from '../src/types'

describe('Type definitions', () => {
  it('should accept valid Phase values', () => {
    const phases: Phase[] = ['RESOLUTION', 'SUMMARY', 'INTERACTION', 'EXECUTION']
    expect(phases).toHaveLength(4)
  })

  it('should accept valid ProvinceBaseData', () => {
    const province: ProvinceBaseData = {
      province_id: 'province_1',
      name: 'Jingzhou',
      population: {
        total: 1000000,
        growth_rate: 0.01,
        labor_ratio: 0.6,
        happiness: 0.7,
      },
      agriculture: {
        crops: [],
        irrigation_level: 0.5,
      },
      commerce: {
        merchant_households: 1000,
        market_prosperity: 0.6,
      },
      trade: {
        trade_volume: 50000,
        trade_route_quality: 0.4,
      },
      military: {
        garrison_size: 5000,
        equipment_level: 0.5,
        morale: 0.6,
        upkeep_per_soldier: 6.0,
        upkeep: 30000,
      },
      taxation: {
        land_tax_rate: 0.03,
        commercial_tax_rate: 0.1,
        tariff_rate: 0.05,
      },
      consumption: {
        civilian_grain_per_capita: 3.0,
        military_grain_per_soldier: 5.0,
      },
      administration: {
        official_count: 200,
        official_salary: 60,
        infrastructure_maintenance_rate: 0.02,
        infrastructure_value: 500000,
        court_levy_amount: 0,
      },
      granary_stock: 100000,
      local_treasury: 50000,
    }
    expect(province.province_id).toBe('province_1')
  })

  it('should accept valid NationalBaseData', () => {
    const national: NationalBaseData = {
      turn: 1,
      imperial_treasury: 1000000,
      national_tax_modifier: 1.0,
      tribute_rate: 0.3,
      provinces: [],
    }
    expect(national.turn).toBe(1)
  })

  it('should accept valid StateResponse', () => {
    const state: StateResponse = {
      game_id: 'game_1',
      current_turn: 1,
      phase: 'RESOLUTION',
      provinces: [],
      imperial_treasury: '1000000',
      active_events_count: 0,
    }
    expect(state.phase).toBe('RESOLUTION')
  })

  it('should accept valid Agent', () => {
    const agent: Agent = {
      id: 'minister_of_revenue',
      name: 'Zhang Ju',
      title: 'Minister of Revenue',
    }
    expect(agent.id).toBe('minister_of_revenue')
  })

  it('should accept valid ChatMessage', () => {
    const message: ChatMessage = {
      id: 'msg_1',
      role: 'user',
      content: 'Hello',
      timestamp: Date.now(),
    }
    expect(message.role).toBe('user')
  })

  it('should accept valid AdvanceResponse', () => {
    const advance: AdvanceResponse = {
      phase: 'SUMMARY',
      turn: 2,
      message: 'Turn advanced',
      reports: null,
      events: null,
    }
    expect(advance.phase).toBe('SUMMARY')
  })
})
