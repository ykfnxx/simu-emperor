"""
Project module - Projects that players can invest in provinces
"""


class Project:
    """Project class"""

    PROJECT_TYPES = {
        'agriculture': {
            'cost': 50,
            'effect_type': 'income_bonus',
            'effect_value': 0.08  # 8% income increase
        },
        'infrastructure': {
            'cost': 80,
            'effect_type': 'development_bonus',
            'effect_value': 0.5  # Development level +0.5
        },
        'tax_relief': {
            'cost': 30,
            'effect_type': 'loyalty_bonus',
            'effect_value': 15  # Loyalty +15
        },
        'security': {
            'cost': 60,
            'effect_type': 'stability_bonus',
            'effect_value': 12  # Stability +12
        }
    }

    def __init__(self, province_id: int, project_type: str, month_created: int):
        """Initialize project

        Args:
            province_id: Province ID
            project_type: Project type (agriculture/infrastructure/tax_relief/security)
            month_created: Creation month
        """
        self.province_id = province_id
        self.project_type = project_type
        config = self.PROJECT_TYPES[project_type]
        self.cost = config['cost']
        self.effect_type = config['effect_type']
        self.effect_value = config['effect_value']
        self.month_created = month_created
        self.status = 'active'

    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        return {
            'province_id': self.province_id,
            'project_type': self.project_type,
            'cost': self.cost,
            'effect_type': self.effect_type,
            'effect_value': self.effect_value,
            'month_created': self.month_created,
            'status': self.status
        }
