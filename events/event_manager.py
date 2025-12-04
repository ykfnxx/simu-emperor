"""
Event Manager

Manages event lifecycle: loading, saving, cleanup, querying
"""

from typing import List, Dict, Optional, Any
from .event_models import Event, EventVisibility, AgentEvent
from .event_effects import calculate_event_modifiers, apply_instant_effects
import json


class EventManager:
    """Event Manager"""

    def __init__(self, db=None):
        """
        Initialize event manager

        Args:
            db: Database instance (optional)
        """
        self.db = db
        self.active_events: List[Event] = []

    def load_active_events(self, current_month: int) -> List[Event]:
        """
        Load active events from database

        Args:
            current_month: Current month

        Returns:
            List of active events
        """
        event_data = self.db.get_active_events(current_month)

        events = []
        for data in event_data:
            try:
                # Parse JSON string
                if isinstance(data.get('instant_effects'), str):
                    import json
                    data['instant_effects'] = json.loads(data['instant_effects'])
                if isinstance(data.get('continuous_effects'), str):
                    import json
                    data['continuous_effects'] = json.loads(data['continuous_effects'])

                event = Event(**data)

                # Check if expired
                if not event.is_expired(current_month):
                    events.append(event)
            except Exception as e:
                print(f"[EventManager] Failed to load event: {e}")
                continue

        self.active_events = events
        return events

    def get_active_events(self, current_month: int) -> List[Event]:
        """
        Get active events (if db is None, return events from memory)

        Args:
            current_month: Current month

        Returns:
            List of active events
        """
        if self.db is None:
            # Clean up expired events
            self.active_events = [e for e in self.active_events if not e.is_expired(current_month)]
            return [e for e in self.active_events if e.is_active]
        else:
            return self.load_active_events(current_month)

    def add_event(self, event: Event) -> None:
        """
        Add event to active events list

        Args:
            event: Event object
        """
        self.active_events.append(event)
        if self.db:
            self.save_event(event)

    def save_event(self, event: Event) -> None:
        """
        Save event to database

        Args:
            event: Event object
        """
        try:
            event_dict = event.dict()

            # Serialize complex fields
            event_dict['instant_effects'] = json.dumps(event_dict.get('instant_effects', []))
            event_dict['continuous_effects'] = json.dumps(event_dict.get('continuous_effects', []))
            event_dict['created_at'] = event_dict['created_at'].isoformat()

            self.db.save_event(event_dict)
        except Exception as e:
            print(f"[EventManager] Failed to save event: {e}")

    def update_event(self, event: Event) -> None:
        """
        Update event status

        Args:
            event: Event object
        """
        try:
            updates = {
                'is_active': event.is_active,
                'is_hidden_by_governor': event.is_hidden_by_governor,
                'hidden_reason': event.hidden_reason,
                'visibility': event.visibility.value,
                'is_fabricated': event.is_fabricated,
                'fabrication_reason': event.fabrication_reason,
                'narrative_consistency_score': event.narrative_consistency_score,
                'verification_status': event.verification_status
            }

            # If end month is set, update it too
            if event.end_month is not None:
                updates['end_month'] = event.end_month

            self.db.update_event(event.event_id, updates)
        except Exception as e:
            print(f"[EventManager] Failed to update event: {e}")

    def cleanup_expired_events(self, current_month: int) -> List[str]:
        """
        Clean up expired events

        Args:
            current_month: Current month

        Returns:
            List of expired event IDs
        """
        expired_ids = []

        for event in self.active_events:
            if event.is_expired(current_month):
                event.is_active = False
                expired_ids.append(event.event_id)
                self.update_event(event)

        # Remove from active list
        self.active_events = [e for e in self.active_events if not e.is_expired(current_month)]

        return expired_ids

    def get_province_modifiers(self, province_id: int, current_month: Optional[int] = None) -> Dict[str, float]:
        """
        Get event modifiers for a province

        Args:
            province_id: Province ID
            current_month: Current month

        Returns:
            Modifier dictionary
        """
        return calculate_event_modifiers(self.active_events, province_id, current_month)

    def get_national_modifiers(self, current_month: Optional[int] = None) -> Dict[str, float]:
        """
        Get national event modifiers

        Args:
            current_month: Current month

        Returns:
            Modifier dictionary
        """
        return calculate_event_modifiers(self.active_events, None, current_month)

    def apply_province_instant_effects(self, province_id: int, province_data: Dict[str, Any],
                                     current_month: Optional[int] = None) -> Dict[str, Any]:
        """
        Apply province event instant effects

        Args:
            province_id: Province ID
            province_data: Province data
            current_month: Current month

        Returns:
            Modified data
        """
        modified_data = province_data.copy()

        # Find instant effects for this province's events
        province_events = [
            e for e in self.active_events
            if e.event_type.value == 'province' and
               e.province_id == province_id and
               e.instant_effects
        ]

        # Filter expired events if month is specified
        if current_month:
            province_events = [e for e in province_events if not e.is_expired(current_month)]

        # Apply instant effects
        for event in province_events:
            modified_data = apply_instant_effects(event, modified_data)

        return modified_data

    def get_events_for_province(self, province_id: int, visibility_filter: Optional[EventVisibility] = None) -> List[Event]:
        """
        Get events related to a province

        Args:
            province_id: Province ID
            visibility_filter: Visibility filter

        Returns:
            List of events
        """
        events = [e for e in self.active_events if e.province_id == province_id]

        if visibility_filter:
            events = [e for e in events if e.visibility == visibility_filter]

        return events

    def get_hidden_events(self) -> List[Event]:
        """
        Get hidden events

        Returns:
            List of hidden events
        """
        return [e for e in self.active_events if e.is_hidden_by_governor]

    def get_agent_generated_events(self) -> List[Event]:
        """
        Get Agent-generated events

        Returns:
            List of Agent-generated events
        """
        return [e for e in self.active_events if e.is_agent_generated]

    def get_fabricated_events(self) -> List[Event]:
        """
        Get fabricated events

        Returns:
            List of fabricated events
        """
        return [e for e in self.active_events if e.is_fabricated]

    def get_event_summary(self, current_month: Optional[int] = None) -> Dict[str, Any]:
        """
        Get event summary

        Args:
            current_month: Current month

        Returns:
            Event summary information
        """
        # Filter expired events
        active_events = self.active_events
        if current_month:
            active_events = [e for e in active_events if not e.is_expired(current_month)]

        national_events = [e for e in active_events if e.event_type.value == 'national']
        province_events = [e for e in active_events if e.event_type.value == 'province']
        agent_events = [e for e in active_events if e.is_agent_generated]
        hidden_events = [e for e in active_events if e.is_hidden_by_governor]
        fabricated_events = [e for e in active_events if e.is_fabricated]

        return {
            'total_active': len(active_events),
            'national_events': len(national_events),
            'province_events': len(province_events),
            'agent_generated_events': len(agent_events),
            'hidden_events': len(hidden_events),
            'fabricated_events': len(fabricated_events),
            'events_by_type': {
                'national': [
                    {
                        'event_id': e.event_id,
                        'name': e.name,
                        'description': e.description,
                        'severity': e.severity
                    } for e in national_events
                ],
                'province': [
                    {
                        'event_id': e.event_id,
                        'name': e.name,
                        'description': e.description,
                        'province_id': e.province_id,
                        'severity': e.severity
                    } for e in province_events
                ]
            }
        }

    def get_monthly_event_report(self, month: int) -> Dict[str, Any]:
        """
        Get event report for specified month

        Args:
            month: Month

        Returns:
            Event report
        """
        # Get events active in this month
        events_in_month = [
            e for e in self.active_events
            if e.start_month <= month <= (e.end_month or month)
        ]

        return {
            'month': month,
            'total_events': len(events_in_month),
            'events': [
                {
                    'event_id': e.event_id,
                    'name': e.name,
                    'type': e.event_type.value,
                    'severity': e.severity
                } for e in events_in_month
            ]
        }
