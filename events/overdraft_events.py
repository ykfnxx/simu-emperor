"""
Overdraft Event Templates

Predefined provincial overdraft event templates
"""

from typing import List, Dict, Any


# Provincial overdraft event templates
OVERDRAFT_EVENTS: List[Dict[str, Any]] = [
    {
        'name': 'Financial Crisis',
        'description': 'Province experiences severe fiscal deficit, unable to pay civil servant salaries, causing government operational difficulties',
        'severity': 0.9,
        'effects': [
            {'scope': 'loyalty', 'operation': 'add', 'value': -20},
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.3}
        ]
    },
    {
        'name': 'Social Unrest',
        'description': 'Due to financial problems causing public service interruptions, citizens begin protesting',
        'severity': 0.8,
        'effects': [
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.4}
        ]
    },
    {
        'name': 'Debt Crisis',
        'description': 'Province unable to repay maturing debts, credit rating downgraded',
        'severity': 0.95,
        'effects': [
            {'scope': 'development_level', 'operation': 'add', 'value': -0.5},
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.5}
        ]
    }
]
