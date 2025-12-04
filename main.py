#!/usr/bin/env python3
"""
EU4 Style Strategy Game - Main Entry
Players act as rulers, indirectly managing provinces through budgets and projects
"""

import sys
from core.game import Game


def main():
    """Main game entry"""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EU4 Style Strategy Game')
    parser.add_argument('--realtime', '-r', action='store_true',
                       help='Use real-time dashboard CLI (refresh mode)')
    args = parser.parse_args()

    print("=" * 60)
    print("EU4 Style Strategy Game - MVP Version")
    print("=" * 60)
    print("\nGame Instructions:")
    print("- You are a ruler managing 1 province")
    print("- View financial reports monthly, invest in provincial projects")
    print("- Local officials may falsify data, handle with care")
    print("- Debug mode (option 3) shows real data")
    if args.realtime:
        print("- Real-time dashboard: refreshes when returning to main menu\n")

    # Create game instance
    game = Game()

    try:
        if args.realtime:
            # Use real-time dashboard CLI (refreshes but not auto-refresh)
            from ui.cli_realtime import RealtimeGameCLI
            RealtimeGameCLI(game).run()
        else:
            # Use traditional CLI
            from ui.cli import GameCLI
            GameCLI(game).run()

    except KeyboardInterrupt:
        print("\n\nGame exited")
        sys.exit(0)


if __name__ == "__main__":
    main()
