#!/usr/bin/env python3
"""
Event System Test

Demonstrate Agent proactive event generation and three-layer data model usage
"""

import asyncio
import sys
sys.path.insert(0, '.')

from events.event_generator import EventGenerator
from events.agent_event_generator import AgentEventGenerator
from events.event_manager import EventManager
from events.event_models import Event
from agents.personality import PERSONALITY_PRESETS, PersonalityTrait
from db.database import Database
from db.event_database import save_event, get_active_events, update_event

# Add new methods to Database class
Database.save_event = save_event
Database.get_active_events = get_active_events
Database.update_event = update_event


async def test_event_system():
    """Test the complete event system"""

    print("=" * 70)
    print("Event System Test")
    print("=" * 70)

    # Initialize
    db = Database(":memory:")  # Use in-memory database
    db.init_database()

    event_manager = EventManager(db)
    event_generator = EventGenerator()
    agent_event_generator = AgentEventGenerator()

    # Create test province data
    provinces = [
        {
            'province_id': 1,
            'name': 'Capital',
            'population': 35000,
            'development_level': 7.0,
            'loyalty': 85,
            'stability': 72,
            'actual_income': 850.0,
            'actual_expenditure: 600.0
        }
    ]

    game_state = {
        'treasury': 1000.0,
        'current_month': 1
    }

    # Test 1: Generate base events
    print("\n[Test 1] Generate base events")
    print("-" * 70)

    events = event_generator.generate_events(game_state, provinces, 2)

    for event in events:
        print(f"Event: {event.name}")
        print(f"  Type: {event.event_type}")
        print(f"  Province: {event.province_id}")
        print(f"  Severity: {event.severity}")
        print(f"  Continuous effects: {len(event.continuous_effects)}")

        for effect in event.continuous_effects:
            print(f"    - {effect.scope}: {effect.operation} {effect.value}")
            if effect.duration:
                print(f"      Lasts {effect.duration} turns")

        # Save event
        event_manager.save_event(event)
        print()

    # Test 2: Agent event generation
    print("\n[Test 2] Agent event generation")
    print("-" * 70)

    # Create Governors with different personalities
    for name, personality in PERSONALITY_PRESETS.items():
        if 'honest' in name:
            # Honest official
            honest_governor = type('Governor', (), {
                'agent_id': f'governor_honest',
                'personality': personality
            })()

            # Generate event
            agent_event = agent_event_generator.generate_agent_event(
                honest_governor,
                provinces[0],
                {'treasury': 1000, 'month': 2, 'central_attention': 0.3}
            )

            if agent_event:
                print(f"Honest governor generated event: {agent_event.name}")
                print(f"  Fabricated: {agent_event.is_fabricated}")
                print(f"  Narrative: {agent_event.narrative[:50]}...")
                event_manager.save_event(agent_event)
            else:
                print("Honest governor chose not to generate event")

        elif 'corrupt' in name:
            # Corrupt official
            corrupt_governor = type('Governor', (), {
                'agent_id': f'governor_corrupt',
                'personality': personality
            })()

            # Generate event
            agent_event = agent_event_generator.generate_agent_event(
                corrupt_governor,
                provinces[1],
                {'treasury': 1000, 'month': 2, 'central_attention': 0.3, 'needs_cover': True}
            )

            if agent_event:
                print(f"Corrupt governor generated event: {agent_event.name}")
                print(f"  Fabricated: {agent_event.is_fabricated}")
                print(f"  Reason: {agent_event.fabrication_reason}")
                print(f"  Narrative: {agent_event.narrative[:50]}...")
                event_manager.save_event(agent_event)
            else:
                print("Corrupt governor chose not to generate event")

    # Test 3: Event effect calculation
    print("\n[Test 3] Event effect calculation")
    print("-" * 70)

    # Load active events
    active_events = event_manager.load_active_events(2)
    print(f"Active events count: {len(active_events)}")

    # Calculate province 1 modifiers
    from events.event_effects import calculate_event_modifiers

    modifiers = calculate_event_modifiers(active_events, province_id=1, current_month=2)

    print(f"\nProvince 1 event modifiers:")
    for key, value in modifiers.items():
        if value != 1.0 and value != 0.0:
            print(f"  {key}: {value:.2f}")

    # Test 4: Database storage and queries
    print("\n[Test 4] Database operations")
    print("-" * 70)

    # Query Agent-generated events
    agent_events = event_manager.get_agent_generated_events()
    print(f"Agent generated events: {len(agent_events)}")

    for event in agent_events:
        print(f"  - {event.name} (fabricated: {event.is_fabricated})")

    # Query hidden events
    hidden_events = event_manager.get_hidden_events()
    print(f"\nHidden events count: {len(hidden_events)}")

    # Get event summary
    summary = event_manager.get_event_summary(2)
    print(f"\nEvent Summary:")
    print(f"  Total active: {summary['total_active']}")
    print(f"  National events: {summary['national_events']}")
    print(f"  Province events: {summary['province_events']}")
    print(f"  Agent generated: {summary['agent_generated_events']}")
    print(f"  Hidden events: {summary['hidden_events']}")

    # Test 5: Event lifecycle management
    print("\n[Test 5] Event lifecycle management")
    print("-" * 70)

    # Simulate time progression
    expired = event_manager.cleanup_expired_events(5)
    print(f"Cleaned up expired events: {len(expired)}")

    # Reload
    active_events = event_manager.load_active_events(5)
    print(f"Month 5 active events: {len(active_events)}")

    print("\n" + "=" * 70)
    print("Test completed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_event_system())
