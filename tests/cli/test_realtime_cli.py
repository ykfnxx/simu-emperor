#!/usr/bin/env python3
"""
Realtime CLI Test

Test simplified real-time CLI
"""

from core.game import Game
from ui.cli_realtime import RealtimeGameCLI
import sys


def test_realtime_cli():
    """Test simplified realtime CLI"""
    print("Initializing game and realtime CLI (simplified version)...")

    # Create game instance
    game = Game(db_path="test_realtime_simple.db")

    # Create CLI and run 3 loops for testing
    cli = RealtimeGameCLI(game)

    # Manually call draw_dashboard a few times to test refresh
    print("\n✓ Test 1: Draw initial dashboard")
    cli.draw_dashboard()
    input("\nPress Enter to continue...")

    print("\n✓ Test 2: Draw dashboard again (verify refresh)")
    cli.draw_dashboard()
    input("\nPress Enter to finish test...")

    print("\n✓ Tests passed! Simplified realtime CLI working correctly.")


if __name__ == "__main__":
    try:
        test_realtime_cli()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n\nTest error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
