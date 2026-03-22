#!/usr/bin/env python3
"""Markdown report generator for benchmark results."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from benchmark.models import MetricResult, ModuleResult

if TYPE_CHECKING:
    pass


class ReportGenerator:
    """Generates Markdown reports from benchmark results."""

    def generate(
        self,
        results: list[ModuleResult],
        output_path: Path | str,
        config: dict | None = None,
    ) -> Path:
        """Generate Markdown report from benchmark results.

        Args:
            results: List of module results
            output_path: Path to save the report
            config: Optional config dict with provider/model info

        Returns:
            Path to the generated report.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build report sections
        sections = [
            self._generate_header(config),
            self._generate_summary(results),
            self._generate_agent_section(results),
            self._generate_memory_section(results),
            self._generate_suggestions(results),
        ]

        # Write report
        content = "\n\n".join(sections)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Report generated: {output_path}")
        return output_path

    def _generate_header(self, config: dict | None) -> str:
        """Generate report header."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider = config.get("provider", "unknown") if config else "unknown"
        model = config.get("model", "unknown") if config else "unknown"

        return f"""# Benchmark 评测报告

**生成时间**: {timestamp}
**模型**: {model}
**Provider**: {provider}"""

    def _generate_summary(self, results: list[ModuleResult]) -> str:
        """Generate execution summary section."""
        lines = ["## 1. 执行概要", "", "| 模块 | 耗时 | 状态 |", "|------|------|------|"]

        for result in results:
            status = "✅" if all(m.passed for m in result.metrics) else "❌"
            duration = f"{result.duration_seconds:.2f}s"
            lines.append(f"| {result.module} | {duration} | {status} |")

        total_duration = sum(r.duration_seconds for r in results)
        lines.append(f"| **总计** | **{total_duration:.2f}s** | |")

        return "\n".join(lines)

    def _generate_agent_section(self, results: list[ModuleResult]) -> str:
        """Generate agent evaluation section."""
        agent_modules = [
            r for r in results if r.module in ("intent_accuracy", "response_perf")
        ]

        if not agent_modules:
            return "## 2. Agent 评测\n\n暂无 Agent 评测结果"

        lines = ["## 2. Agent 评测"]

        # Intent accuracy
        intent = next((r for r in agent_modules if r.module == "intent_accuracy"), None)
        if intent:
            lines.extend(
                [
                    "",
                    "### 2.1 意图识别准确率",
                    "",
                    self._format_metrics_table(intent.metrics),
                ]
            )

        # Response performance
        perf = next((r for r in agent_modules if r.module == "response_perf"), None)
        if perf:
            lines.extend(
                [
                    "",
                    "### 2.2 响应性能",
                    "",
                    self._format_metrics_table(perf.metrics),
                ]
            )

        return "\n".join(lines)

    def _generate_memory_section(self, results: list[ModuleResult]) -> str:
        """Generate memory system section."""
        memory_modules = [
            r for r in results if r.module in ("retrieval", "compression", "cross_session")
        ]

        if not memory_modules:
            return "## 3. 记忆系统评测\n\n暂无记忆系统评测结果"

        lines = ["## 3. 记忆系统评测"]

        # Retrieval
        retrieval = next((r for r in memory_modules if r.module == "retrieval"), None)
        if retrieval:
            lines.extend(
                [
                    "",
                    "### 3.1 检索性能",
                    "",
                    self._format_metrics_table(retrieval.metrics),
                ]
            )

        # Compression
        compression = next((r for r in memory_modules if r.module == "compression"), None)
        if compression:
            lines.extend(
                [
                    "",
                    "### 3.2 压缩保真度",
                    "",
                    self._format_metrics_table(compression.metrics),
                ]
            )

        # Cross-session
        cross_session = next((r for r in memory_modules if r.module == "cross_session"), None)
        if cross_session:
            lines.extend(
                [
                    "",
                    "### 3.3 跨会话一致性",
                    "",
                    self._format_metrics_table(cross_session.metrics),
                ]
            )

        return "\n".join(lines)

    def _format_metrics_table(self, metrics: list[MetricResult]) -> str:
        """Format metrics as a Markdown table."""
        lines = ["| 指标 | 值 | 目标 | 状态 |", "|------|-----|------|------|"]

        for metric in metrics:
            status = "✅" if metric.passed else "❌"

            # Format value based on unit
            if metric.unit == "%":
                value_str = f"{metric.value:.1f}%"
                target_str = f"≥{metric.target:.0f}%"
            elif metric.unit == "ms":
                value_str = f"{metric.value:.0f}ms"
                target_str = f"≤{metric.target:.0f}ms"
            elif metric.unit == "s":
                value_str = f"{metric.value:.2f}s"
                target_str = f"≤{metric.target:.1f}s"
            else:
                value_str = f"{metric.value:.2f}"
                target_str = f"{metric.target:.2f}"

            lines.append(f"| {metric.name} | {value_str} | {target_str} | {status} |")

        return "\n".join(lines)

    def _generate_suggestions(self, results: list[ModuleResult]) -> str:
        """Generate optimization suggestions based on metrics."""
        lines = ["## 4. 优化建议", ""]

        if not results:
            lines.append("暂无优化建议")
            return "\n".join(lines)

        suggestions = []

        for result in results:
            for metric in result.metrics:
                if metric.passed:
                    suggestions.append(f"- **{metric.name}**: 达标，无需优化")
                elif metric.value < metric.target * 0.8:
                    suggestions.append(
                        f"- **{metric.name}**: 严重低于目标 ({metric.value:.1f} < {metric.target * 0.8:.1f})，建议优先检查"
                    )
                else:
                    suggestions.append(f"- **{metric.name}**: 略低于目标，建议优化")

        lines.extend(suggestions if suggestions else ["所有指标均已达标"])

        return "\n".join(lines)

    def _generate_histogram(
        self,
        values: list[float],
        bins: int = 5,
        width: int = 40,
        unit: str = "",
    ) -> str:
        """Generate ASCII histogram for value distribution.

        Args:
            values: List of values to plot
            bins: Number of bins
            width: Maximum bar width in characters
            unit: Unit suffix for labels

        Returns:
            ASCII histogram as string.
        """
        if not values:
            return "No data"

        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            return f"All values: {min_val:.2f}{unit}"

        # Create bins
        bin_width = (max_val - min_val) / bins
        bin_counts = [0] * bins

        for v in values:
            idx = min(int((v - min_val) / bin_width), bins - 1)
            bin_counts[idx] += 1

        max_count = max(bin_counts)

        # Generate histogram
        lines = ["Latency Distribution:"]

        for i, count in enumerate(bin_counts):
            low = min_val + i * bin_width
            high = min_val + (i + 1) * bin_width

            bar_len = int((count / max_count) * width) if max_count > 0 else 0
            bar = "█" * bar_len

            lines.append(f"{low:.1f}-{high:.1f}{unit} |{bar} ({count})")

        return "\n".join(lines)
