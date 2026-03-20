#!/usr/bin/env python3
"""CLI entry point for the benchmark system."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from benchmark.config import BenchmarkConfig


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m benchmark",
        description="Benchmark system for 皇帝模拟器 - evaluates Agent and Memory system performance",
    )
    parser.add_argument(
        "--module",
        choices=["agent", "memory", "all"],
        default="all",
        help="Which module to benchmark (agent, memory, or all)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat the benchmark",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for the Markdown report (default: auto-generated)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to benchmark config file (config.benchmark.yaml)",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        # Load configuration
        config = BenchmarkConfig.load(args.config)

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            output_path = Path(f"benchmark/reports/benchmark-{timestamp}.md")

        # Placeholder - runner not yet implemented
        print(f"Benchmark CLI ready.")
        print(f"  Module: {args.module}")
        print(f"  Repeat: {args.repeat}")
        print(f"  Output: {output_path}")
        print(f"  Config: {config.provider}/{config.model}")
        print()
        print("Runner not yet implemented. Please implement benchmark/runner.py first.")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
