#!/usr/bin/env python3
"""Orchestration runner for the benchmark system."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from benchmark.config import BenchmarkConfig
from benchmark.models import ModuleResult

if TYPE_CHECKING:
    pass


class BenchmarkRunner:
    """Orchestrates benchmark execution across all modules."""

    def __init__(self, config: BenchmarkConfig | None = None):
        """Initialize the benchmark runner.

        Args:
            config: Benchmark configuration. If None, loads from default sources.
        """
        self.config = config or BenchmarkConfig.load()
        self.results: list[ModuleResult] = []

    async def run(
        self,
        module: Literal["agent", "memory", "all"] = "all",
        repeat: int = 1,
    ) -> list[ModuleResult]:
        """Run benchmark modules sequentially.

        Args:
            module: Which module to run (agent, memory, or all)
            repeat: Number of times to repeat the benchmark

        Returns:
            List of ModuleResult from all runs
        """
        self.results = []

        for i in range(repeat):
            if repeat > 1:
                print(f"\n=== Run {i + 1}/{repeat} ===")

            if module in ("agent", "all"):
                agent_results = await self._run_agent_modules()
                self.results.extend(agent_results)

            if module in ("memory", "all"):
                memory_results = await self._run_memory_modules()
                self.results.extend(memory_results)

        return self.results

    async def _run_agent_modules(self) -> list[ModuleResult]:
        from benchmark.agent.intent_accuracy import IntentAccuracyEvaluator
        from benchmark.agent.response_perf import ResponsePerfEvaluator
        from benchmark.agent.multi_agent import MultiAgentEvaluator

        results = []
        evaluators = [
            ("intent_accuracy", IntentAccuracyEvaluator(self.config)),
            ("response_perf", ResponsePerfEvaluator(self.config)),
            ("multi_agent", MultiAgentEvaluator(self.config)),
        ]

        for module_name, evaluator in evaluators:
            start = time.perf_counter()
            result = await evaluator.evaluate()
            results.append(result)
            print(f"  [{module_name}] Completed in {result.duration_seconds:.2f}s")

        return results

    async def _run_memory_modules(self) -> list[ModuleResult]:
        from benchmark.memory.retrieval import RetrievalEvaluator
        from benchmark.memory.compression import CompressionEvaluator
        from benchmark.memory.cross_session import CrossSessionEvaluator

        results = []
        evaluators = [
            ("retrieval", RetrievalEvaluator(self.config)),
            ("compression", CompressionEvaluator(self.config)),
            ("cross_session", CrossSessionEvaluator(self.config)),
        ]

        for module_name, evaluator in evaluators:
            start = time.perf_counter()
            result = await evaluator.evaluate()
            results.append(result)
            print(f"  [{module_name}] Completed in {result.duration_seconds:.2f}s")

        return results

    def save_results(self, output_dir: Path | None = None) -> Path:
        """Save results to JSON file.

        Saves to: benchmark/reports/raw/benchmark-YYYY-MM-DD-NNN.json
        NNN is a sequence number to avoid collisions.

        Args:
            output_dir: Directory to save results. If None, uses default.

        Returns:
            Path to the saved JSON file.
        """
        if output_dir is None:
            output_dir = Path(__file__).parent / "reports" / "raw"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with sequence number
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"benchmark-{date_str}"

        # Find next available sequence number
        seq = 1
        while True:
            filename = f"{base_name}-{seq:03d}.json"
            filepath = output_dir / filename
            if not filepath.exists():
                break
            seq += 1

        # Build JSON structure
        data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "provider": self.config.provider,
                "model": self.config.model,
            },
            "modules": [result.to_dict() for result in self.results],
        }

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {filepath}")
        return filepath

    def get_summary(self) -> dict[str, Any]:
        """Get summary of benchmark results."""
        if not self.results:
            return {"status": "no_results", "modules": 0}

        total_duration = sum(r.duration_seconds for r in self.results)
        passed_modules = sum(1 for r in self.results if all(m.passed for m in r.metrics))

        return {
            "status": "completed",
            "modules": len(self.results),
            "passed_modules": passed_modules,
            "total_duration_seconds": total_duration,
        }
