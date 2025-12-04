"""
Event Template Definitions

Define all available event templates for dynamic game event generation
"""

from typing import Dict, List, Any

# Event template data structure
EVENT_TEMPLATES = {
    # National events
    'national': [
        # Economic boom
        {
            'id': 'economic_boom',
            'name': 'Economic Boom',
            'description': 'National economy enters boom period, all provinces see increased income',
            'conditions': {
                'treasury': {'min': 500}
            },
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'income',
                    'operation': 'multiply',
                    'value': 1.2,
                    'duration': 3
                }
            ],
            'duration': 3,
            'metadata': {
                'category': 'economy',
                'rarity': 'rare'
            }
        },
        # Economic crisis
        {
            'id': 'economic_crisis',
            'name': 'Economic Crisis',
            'description': 'Economic crisis erupts, all provinces see decreased income',
            'conditions': {
                'treasury': {'max': 200}
            },
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'income',
                    'operation': 'multiply',
                    'value': 0.7,
                    'duration': 4
                }
            ],
            'duration': 4,
            'metadata': {
                'category': 'economy',
                'rarity': 'rare'
            }
        },
        # Policy reform
        {
            'id': 'policy_reform',
            'name': 'Policy Reform',
            'description': 'Central government implements new policies, improving administrative efficiency',
            'conditions': {},
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'expenditure',
                    'operation': 'multiply',
                    'value': 0.9,
                    'duration': 6
                }
            ],
            'duration': 6,
            'metadata': {
                'category': 'policy',
                'rarity': 'uncommon'
            }
        },
        # Natural disaster
        {
            'id': 'natural_disaster',
            'name': 'Natural Disaster',
            'description': 'Multiple provinces suffer natural disasters, requiring additional repair expenses',
            'conditions': {},
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'expenditure',
                    'operation': 'multiply',
                    'value': 1.3,
                    'duration': 2
                }
            ],
            'duration': 2,
            'metadata': {
                'category': 'disaster',
                'rarity': 'common'
            }
        }
    ],
    # Province events
    'province': [
        # Bumper harvest
        {
            'id': 'harvest_bumper',
            'name': 'Bumper Harvest',
            'description': 'This province has an agricultural bumper harvest, increasing income',
            'conditions': {
                'stability': {'min': 40}
            },
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'income',
                    'operation': 'multiply',
                    'value': 1.5,
                    'duration': 2
                }
            ],
            'duration': 2,
            'metadata': {
                'category': 'agriculture',
                'rarity': 'common'
            }
        },
        # Plague outbreak
        {
            'id': 'plague_outbreak',
            'name': 'Plague Outbreak',
            'description': 'This province experiences a plague outbreak, reducing population and increasing expenses',
            'conditions': {
                'population': {'min': 50000}
            },
            'instant_effects': [
                {
                    'scope': 'population',
                    'operation': 'add',
                    'value': -5000
                }
            ],
            'continuous_effects': [
                {
                    'scope': 'expenditure',
                    'operation': 'multiply',
                    'value': 1.4,
                    'duration': 3
                }
            ],
            'duration': 3,
            'metadata': {
                'category': 'disease',
                'rarity': 'uncommon'
            }
        },
        # Trade boom
        {
            'id': 'trade_boom',
            'name': 'Trade Boom',
            'description': 'This province experiences commercial prosperity, increasing income',
            'conditions': {
                'development_level': {'min': 6}
            },
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'income',
                    'operation': 'multiply',
                    'value': 1.25,
                    'duration': 4
                }
            ],
            'duration': 4,
            'metadata': {
                'category': 'commerce',
                'rarity': 'uncommon'
            }
        },
        # Rebellion
        {
            'id': 'rebellion',
            'name': 'Rebellion',
            'description': 'This province experiences rebellion, decreasing stability and increasing expenses',
            'conditions': {
                'stability': {'max': 30}
            },
            'instant_effects': [
                {
                    'scope': 'stability',
                    'operation': 'multiply',
                    'value': 0.7
                }
            ],
            'continuous_effects': [
                {
                    'scope': 'expenditure',
                    'operation': 'multiply',
                    'value': 1.5,
                    'duration': 3
                }
            ],
            'duration': 3,
            'metadata': {
                'category': 'unrest',
                'rarity': 'common'
            }
        },
        # Official appointment
        {
            'id': 'official_appointment',
            'name': 'Official Appointment',
            'description': "This province's key officials are replaced, increasing loyalty",
            'conditions': {},
            'instant_effects': [],
            'continuous_effects': [
                {
                    'scope': 'loyalty',
                    'operation': 'add',
                    'value': 20,
                    'duration': 5
                }
            ],
            'duration': 5,
            'metadata': {
                'category': 'personnel',
                'rarity': 'common'
            }
        },
        # Technological breakthrough
        {
            'id': 'technological_breakthrough',
            'name': 'Technological Breakthrough',
            'description': 'This province experiences technological innovation, increasing development level',
            'conditions': {
                'development_level': {'min': 4, 'max': 8}
            },
            'instant_effects': [
                {
                    'scope': 'development_level',
                    'operation': 'add',
                    'value': 1.0
                }
            ],
            'continuous_effects': [],
            'duration': 1,
            'metadata': {
                'category': 'technology',
                'rarity': 'rare'
            }
        },
        # Tax adjustment
        {
            'id': 'tax_adjustment',
            'name': 'Tax Adjustment',
            'description': 'This province adjusts tax policies',
            'conditions': {},
            'instant_effects': [
                {
                    'scope': 'loyalty',
                    'operation': 'add',
                    'value': -10
                }
            ],
            'continuous_effects': [
                {
                    'scope': 'income',
                    'operation': 'multiply',
                    'value': 1.15,
                    'duration': 6
                }
            ],
            'duration': 6,
            'metadata': {
                'category': 'taxation',
                'rarity': 'common'
            }
        },
        # Border conflict
        {
            'id': 'border_conflict',
            'name': 'Border Conflict',
            'description': "This province's border experiences conflict, increasing expenses and decreasing stability",
            'conditions': {
                'name': 'Border Province'
            },
            'instant_effects': [
                {
                    'scope': 'stability',
                    'operation': 'add',
                    'value': -15
                }
            ],
            'continuous_effects': [
                {
                    'scope': 'expenditure',
                    'operation': 'multiply',
                    'value': 1.2,
                    'duration': 4
                }
            ],
            'duration': 4,
            'metadata': {
                'category': 'military',
                'rarity': 'uncommon'
            }
        }
    ]
}

# Events categorized by type (for statistics and analysis)
EVENT_CATEGORIES = {
    'economy': ['economic_boom', 'economic_crisis', 'tax_adjustment'],
    'agriculture': ['harvest_bumper'],
    'commerce': ['trade_boom'],
    'policy': ['policy_reform'],
    'disease': ['plague_outbreak'],
    'unrest': ['rebellion'],
    'disaster': ['natural_disaster'],
    'personnel': ['official_appointment'],
    'technology': ['technological_breakthrough'],
    'military': ['border_conflict']
}

# Event rarity definitions
RARITY_WEIGHTS = {
    'common': 0.6,      # 60% probability
    'uncommon': 0.3,    # 30% probability
    'rare': 0.1         # 10% probability
}