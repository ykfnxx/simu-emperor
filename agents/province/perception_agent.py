"""
PerceptionAgent - First stage in Province Agent pipeline

Responsibilities:
- Read and organize historical data
- Build layered summaries (monthly/quarterly/annual)
- Index critical events
- Analyze trends and risks
- Generate LLM-powered summaries
"""

import json
from typing import List, Dict, Any, Optional
from agents.base import BaseAgent
from agents.province.models import (
    PerceptionContext, MonthlyDetailedData, QuarterlySummary,
    AnnualSummary, EventIndex, TrendAnalysis, TrendDirection, RiskLevel,
    EventSummary
)
from db.database import Database


class PerceptionAgent(BaseAgent):
    """
    PerceptionAgent - First stage in Province Agent pipeline

    Responsible for:
    - Reading and organizing historical data
    - Building layered summaries (monthly/quarterly/annual)
    - Indexing critical events
    - Analyzing trends and providing structured context to DecisionAgent
    """

    def __init__(self, agent_id: str, config: Dict[str, Any], db: Database):
        """
        Initialize PerceptionAgent

        Args:
            agent_id: Unique agent identifier
            config: Configuration dict with llm_config
            db: Database instance
        """
        super().__init__(agent_id, config)
        self.db = db
        self.province_id = config.get('province_id')

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent (called after creation)"""
        pass

    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start (not used in perception phase)"""
        pass

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action (not used in perception phase)"""
        return None

    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'mode': self.mode.value,
            'llm_enabled': self.llm_config.enabled
        }

    # ========== Main Perception Method ==========

    async def perceive(
        self,
        province_id: int,
        current_month: int,
        current_year: int
    ) -> PerceptionContext:
        """
        Main perception entry point

        Args:
            province_id: Province identifier
            current_month: Current game month (1-indexed)
            current_year: Current year

        Returns:
            PerceptionContext with layered historical data
        """
        # Step 1: Build monthly detailed data (last month)
        # Calculate previous month correctly (handles year boundary)
        prev_month, prev_year = self._calculate_previous_month(current_month, current_year)
        recent_data = await self._build_monthly_detailed(
            province_id, prev_month, prev_year
        )

        # Step 2: Build quarterly summaries (last 4 quarters)
        quarterly_summaries = await self._build_quarterly_summaries(
            province_id, current_month, current_year
        )

        # Step 3: Build annual summaries (last 3 years)
        annual_summaries = await self._build_annual_summaries(
            province_id, current_year
        )

        # Step 4: Index critical events
        critical_events = await self._index_critical_events(
            province_id, months_lookback=12
        )

        # Step 5: Analyze trends
        trends = await self._analyze_trends(
            recent_data, quarterly_summaries, annual_summaries
        )

        # Step 6: Assess data quality
        data_quality, warnings = self._assess_data_quality(
            recent_data, quarterly_summaries, annual_summaries
        )

        return PerceptionContext(
            province_id=province_id,
            province_name=await self._get_province_name(province_id),
            current_month=current_month,
            current_year=current_year,
            recent_data=recent_data,
            quarterly_summaries=quarterly_summaries,
            annual_summaries=annual_summaries,
            critical_events=critical_events,
            trends=trends,
            data_quality=data_quality,
            warnings=warnings
        )

    # ========== Helper Methods ==========

    async def _get_province_name(self, province_id: int) -> str:
        """Get province name from database"""
        province = self.db.get_province(province_id)
        if province:
            return province['name']
        return f"Province {province_id}"

    def _calculate_previous_month(self, current_month: int, current_year: int) -> tuple:
        """
        Calculate the previous month and year correctly

        Handles two conventions:
        1. current_month is 1-12 (month within year)
        2. current_month is continuous (13 = Jan year 2, 24 = Dec year 2)

        Args:
            current_month: Current month (can be 1-12 or continuous)
            current_year: Current year

        Returns:
            Tuple of (previous_month, previous_year) where month is 1-12
        """
        # If month is in the continuous format (> 12), convert to (month, year) first
        if current_month > 12:
            # Convert continuous month to (month_in_year, year)
            month_in_year = (current_month - 1) % 12 + 1
            year = (current_month - 1) // 12 + 1

            # Now calculate previous month
            if month_in_year > 1:
                return month_in_year - 1, year
            else:
                return 12, year - 1
        else:
            # Standard format: month is 1-12
            if current_month > 1:
                return current_month - 1, current_year
            else:
                # January -> December of previous year
                return 12, current_year - 1

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response for structured output"""
        return None  # Not used in PerceptionAgent

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response for summary generation"""
        if "quarterly" in prompt.lower():
            return "Quarterly performance showed income growth with improving loyalty indicators."
        elif "annual" in prompt.lower():
            return "Annual performance demonstrated steady growth despite occasional challenges."
        return "Summary generated from provincial data."

    # ========== Data Building Methods ==========

    async def _build_monthly_detailed(
        self,
        province_id: int,
        target_month: int,
        target_year: int
    ) -> MonthlyDetailedData:
        """Build complete monthly data for the most recent month"""
        # Normalize month/year (handle year rollover)
        if target_month <= 0:
            target_month = 12 + target_month
            target_year -= 1

        # Try to load from database
        report = self.db.get_monthly_report(province_id, target_month, target_year)

        if report is None:
            # No history data - return defaults
            province = self.db.get_province(province_id)
            return self._create_default_monthly_data(
                province, target_month, target_year
            )

        # Load events for this month
        events = self.db.get_events_for_month(province_id, target_month, target_year)
        event_summaries = [
            EventSummary(
                event_id=e['event_id'],
                event_type=e['event_type'],
                name=e['name'],
                severity=e.get('severity', 0.5),
                month=target_month,
                year=target_year,
                description=e.get('description')
            )
            for e in events
        ]

        return MonthlyDetailedData(
            month=target_month,
            year=target_year,
            population=report.get('population', 0),
            development_level=report.get('development_level', 5.0),
            loyalty=report.get('loyalty', 50.0),
            stability=report.get('stability', 50.0),
            actual_income=report.get('actual_income', 0.0),
            actual_expenditure=report.get('actual_expenditure', 0.0),
            reported_income=report.get('reported_income', 0.0),
            reported_expenditure=report.get('reported_expenditure', 0.0),
            actual_surplus=report.get('actual_income', 0.0) - report.get('actual_expenditure', 0.0),
            reported_surplus=report.get('reported_income', 0.0) - report.get('reported_expenditure', 0.0),
            events=event_summaries
        )

    async def _build_quarterly_summaries(
        self,
        province_id: int,
        current_month: int,
        current_year: int
    ) -> List[QuarterlySummary]:
        """Build quarterly summaries for the last 4 quarters"""
        # Handle continuous month counting (e.g., month 13 = Jan of year 2)
        if current_month > 12:
            month_in_year = (current_month - 1) % 12 + 1
            year = (current_month - 1) // 12 + 1
        else:
            month_in_year = current_month
            year = current_year

        current_quarter = (month_in_year - 1) // 3 + 1
        quarters_to_build = []

        # Generate last 4 quarters
        for i in range(1, 5):
            q = current_quarter - i
            y = year

            if q <= 0:
                q = 4 + q
                y -= 1

            if y <= 0:  # Skip year 0 and negative
                continue

            quarters_to_build.append((q, y))

        summaries = []

        for quarter, year in quarters_to_build:
            # Try to load existing summary
            db_summary = self.db.get_quarterly_summary(province_id, quarter, year)

            if db_summary is None:
                # Generate on-the-fly
                summary = await self._generate_quarterly_summary(
                    province_id, quarter, year
                )
                if summary:
                    # Save to database (includes LLM-generated summary)
                    self.db.save_quarterly_summary(
                        province_id, quarter, year,
                        summary.avg_income, summary.median_income,
                        summary.avg_expenditure, summary.median_expenditure,
                        summary.total_surplus, summary.income_trend.value,
                        summary.expenditure_trend.value, summary.loyalty_change,
                        summary.stability_change, summary.major_events,
                        summary.special_event_types, summary.summary
                    )
                    summaries.append(summary)
            else:
                # Use existing summary from database
                summary = QuarterlySummary(
                    quarter=db_summary['quarter'],
                    year=db_summary['year'],
                    avg_income=db_summary['avg_income'] or 0.0,
                    median_income=db_summary['median_income'] or 0.0,
                    avg_expenditure=db_summary['avg_expenditure'] or 0.0,
                    median_expenditure=db_summary['median_expenditure'] or 0.0,
                    total_surplus=db_summary['total_surplus'] or 0.0,
                    income_trend=TrendDirection(db_summary['income_trend']) if db_summary['income_trend'] else TrendDirection.STABLE,
                    expenditure_trend=TrendDirection(db_summary['expenditure_trend']) if db_summary['expenditure_trend'] else TrendDirection.STABLE,
                    loyalty_change=db_summary['loyalty_change'] or 0.0,
                    stability_change=db_summary['stability_change'] or 0.0,
                    major_events=json.loads(db_summary['major_events']) if db_summary.get('major_events') else [],
                    special_event_types=json.loads(db_summary['special_event_types']) if db_summary.get('special_event_types') else [],
                    summary=db_summary.get('summary', 'No summary available.')
                )
                summaries.append(summary)

        return summaries

    async def _generate_quarterly_summary(
        self,
        province_id: int,
        quarter: int,
        year: int
    ) -> Optional[QuarterlySummary]:
        """Generate quarterly summary from monthly data"""
        # Calculate month range
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3

        # Query monthly data
        monthly_reports = []
        for month in range(start_month, end_month + 1):
            report = self.db.get_monthly_report(province_id, month, year)
            if report:
                monthly_reports.append(report)

        if not monthly_reports:
            return None

        # Calculate statistics
        incomes = [r.get('actual_income', 0) for r in monthly_reports if r.get('actual_income')]
        expenditures = [r.get('actual_expenditure', 0) for r in monthly_reports if r.get('actual_expenditure')]

        if not incomes or not expenditures:
            return None

        avg_income = sum(incomes) / len(incomes)
        median_income = sorted(incomes)[len(incomes) // 2]
        avg_expenditure = sum(expenditures) / len(expenditures)
        median_expenditure = sorted(expenditures)[len(expenditures) // 2]
        total_surplus = sum(incomes) - sum(expenditures)

        # Calculate trends
        prev_quarter, prev_year = (quarter - 1, year) if quarter > 1 else (4, year - 1)
        prev_summary = self.db.get_quarterly_summary(province_id, prev_quarter, prev_year)

        income_trend = TrendDirection.STABLE
        expenditure_trend = TrendDirection.STABLE

        if prev_summary and prev_summary.get('avg_income'):
            income_change = (avg_income - prev_summary['avg_income']) / max(prev_summary['avg_income'], 1)
            if income_change > 0.05:
                income_trend = TrendDirection.INCREASING
            elif income_change < -0.05:
                income_trend = TrendDirection.DECREASING

        if prev_summary and prev_summary.get('avg_expenditure'):
            expenditure_change = (avg_expenditure - prev_summary['avg_expenditure']) / max(prev_summary['avg_expenditure'], 1)
            if expenditure_change > 0.05:
                expenditure_trend = TrendDirection.INCREASING
            elif expenditure_change < -0.05:
                expenditure_trend = TrendDirection.DECREASING

        # Calculate loyalty/stability change
        first_loyalty = monthly_reports[0].get('loyalty', 50.0)
        last_loyalty = monthly_reports[-1].get('loyalty', 50.0)
        loyalty_change = last_loyalty - first_loyalty

        first_stability = monthly_reports[0].get('stability', 50.0)
        last_stability = monthly_reports[-1].get('stability', 50.0)
        stability_change = last_stability - first_stability

        # Extract major events
        major_events = []
        special_event_types = []

        for report in monthly_reports:
            events = self.db.get_events_for_month(province_id, report['month'], year)
            for event in events:
                severity = event.get('severity', 0.5)
                if severity > 0.5:
                    major_events.append(f"{event['name']} (Month {report['month']})")
                if event['event_type'] in ['rebellion', 'war', 'disaster', 'crisis']:
                    special_event_types.append(event['event_type'])

        # Generate LLM summary
        summary_data = {
            'quarter': quarter,
            'year': year,
            'avg_income': avg_income,
            'income_change': ((avg_income - prev_summary['avg_income']) / max(prev_summary['avg_income'], 1) * 100) if prev_summary and prev_summary.get('avg_income') else 0,
            'loyalty_change': loyalty_change,
            'stability_change': stability_change,
            'major_events': major_events,
            'special_event_types': special_event_types
        }

        summary = await self._generate_quarterly_summary_with_llm(summary_data)

        return QuarterlySummary(
            quarter=quarter,
            year=year,
            avg_income=avg_income,
            median_income=median_income,
            avg_expenditure=avg_expenditure,
            median_expenditure=median_expenditure,
            total_surplus=total_surplus,
            income_trend=income_trend,
            expenditure_trend=expenditure_trend,
            loyalty_change=loyalty_change,
            stability_change=stability_change,
            major_events=list(set(major_events)),
            special_event_types=list(set(special_event_types)),
            summary=summary
        )

    async def _build_annual_summaries(
        self,
        province_id: int,
        current_year: int
    ) -> List[AnnualSummary]:
        """Build annual summaries for the last 3 years"""
        years_to_build = [current_year - 1, current_year - 2, current_year - 3]
        summaries = []

        for year in years_to_build:
            if year <= 0:
                continue

            db_summary = self.db.get_annual_summary(province_id, year)

            if db_summary is None:
                summary = await self._generate_annual_summary(province_id, year)
                if summary:
                    self.db.save_annual_summary(
                        province_id, year,
                        summary.total_income, summary.total_expenditure,
                        summary.avg_monthly_income, summary.avg_monthly_expenditure,
                        summary.total_surplus, summary.population_change,
                        summary.development_change, summary.loyalty_start,
                        summary.loyalty_end, summary.loyalty_change,
                        summary.major_events, summary.disaster_count,
                        summary.rebellion_count, summary.performance_rating,
                        summary.summary
                    )
                    summaries.append(summary)
            else:
                summary = AnnualSummary(
                    year=db_summary['year'],
                    total_income=db_summary['total_income'] or 0.0,
                    total_expenditure=db_summary['total_expenditure'] or 0.0,
                    avg_monthly_income=db_summary['avg_monthly_income'] or 0.0,
                    avg_monthly_expenditure=db_summary['avg_monthly_expenditure'] or 0.0,
                    total_surplus=db_summary['total_surplus'] or 0.0,
                    population_change=db_summary['population_change'] or 0,
                    development_change=db_summary['development_change'] or 0.0,
                    loyalty_start=db_summary['loyalty_start'] or 50.0,
                    loyalty_end=db_summary['loyalty_end'] or 50.0,
                    loyalty_change=db_summary['loyalty_change'] or 0.0,
                    major_events=json.loads(db_summary['major_events']) if db_summary.get('major_events') else [],
                    disaster_count=db_summary.get('disaster_count', 0),
                    rebellion_count=db_summary.get('rebellion_count', 0),
                    performance_rating=db_summary.get('performance_rating', 'average'),
                    summary=db_summary.get('summary', 'No summary available.')
                )
                summaries.append(summary)

        return summaries

    async def _generate_annual_summary(
        self,
        province_id: int,
        year: int
    ) -> Optional[AnnualSummary]:
        """Generate annual summary from quarterly/monthly data"""
        # Query monthly reports for the year
        monthly_reports = []
        for month in range(1, 13):
            report = self.db.get_monthly_report(province_id, month, year)
            if report:
                monthly_reports.append(report)

        if not monthly_reports:
            return None

        # Calculate annual statistics
        incomes = [r.get('actual_income', 0) for r in monthly_reports if r.get('actual_income')]
        expenditures = [r.get('actual_expenditure', 0) for r in monthly_reports if r.get('actual_expenditure')]

        if not incomes:
            return None

        total_income = sum(incomes)
        total_expenditure = sum(expenditures) if expenditures else 0
        total_surplus = total_income - total_expenditure
        avg_monthly_income = total_income / len(incomes)
        avg_monthly_expenditure = total_expenditure / len(expenditures) if expenditures else 0

        # Calculate changes
        first_pop = monthly_reports[0].get('population', 50000)
        last_pop = monthly_reports[-1].get('population', 50000)
        population_change = last_pop - first_pop

        first_dev = monthly_reports[0].get('development_level', 5.0)
        last_dev = monthly_reports[-1].get('development_level', 5.0)
        development_change = last_dev - first_dev

        loyalty_start = monthly_reports[0].get('loyalty', 50.0)
        loyalty_end = monthly_reports[-1].get('loyalty', 50.0)
        loyalty_change = loyalty_end - loyalty_start

        # Extract major events
        major_events = []
        disaster_count = 0
        rebellion_count = 0

        for report in monthly_reports:
            events = self.db.get_events_for_month(province_id, report['month'], year)
            for event in events:
                if event.get('severity', 0.5) > 0.7:
                    major_events.append(f"{event['name']} (Month {report['month']})")

                if event['event_type'] == 'disaster':
                    disaster_count += 1
                elif event['event_type'] == 'rebellion':
                    rebellion_count += 1

        # Performance rating
        if loyalty_change > 10 and total_surplus > 0:
            performance_rating = "excellent"
        elif loyalty_change > 5 or total_surplus > 0:
            performance_rating = "good"
        elif loyalty_change < -10 or total_surplus < 0:
            performance_rating = "poor"
        else:
            performance_rating = "average"

        # Generate LLM summary
        summary_data = {
            'year': year,
            'total_income': total_income,
            'avg_monthly_income': avg_monthly_income,
            'total_surplus': total_surplus,
            'loyalty_change': loyalty_change,
            'disaster_count': disaster_count,
            'rebellion_count': rebellion_count
        }

        summary = await self._generate_annual_summary_with_llm(summary_data)

        return AnnualSummary(
            year=year,
            total_income=total_income,
            total_expenditure=total_expenditure,
            avg_monthly_income=avg_monthly_income,
            avg_monthly_expenditure=avg_monthly_expenditure,
            total_surplus=total_surplus,
            population_change=population_change,
            development_change=development_change,
            loyalty_start=loyalty_start,
            loyalty_end=loyalty_end,
            loyalty_change=loyalty_change,
            major_events=list(set(major_events)),
            disaster_count=disaster_count,
            rebellion_count=rebellion_count,
            performance_rating=performance_rating,
            summary=summary
        )

    async def _index_critical_events(
        self,
        province_id: int,
        months_lookback: int = 12
    ) -> List[EventIndex]:
        """Index critical events for quick reference"""
        events = self.db.get_special_events(
            province_id=province_id,
            categories=['rebellion', 'war', 'disaster', 'crisis'],
            limit=8
        )

        return [
            EventIndex(
                index_id=e['index_id'],
                event_id=e['event_id'],
                event_category=e['event_category'],
                event_name=e['event_name'],
                severity=e['severity'],
                month=e['month'],
                year=e['year'],
                impact_description=e['impact_description'],
                is_resolved=bool(e['is_resolved'])
            )
            for e in events
        ]

    async def _analyze_trends(
        self,
        recent_data: MonthlyDetailedData,
        quarterly_summaries: List[QuarterlySummary],
        annual_summaries: List[AnnualSummary]
    ) -> TrendAnalysis:
        """Analyze trends and identify risks/opportunities"""
        # Default values if no data
        if not quarterly_summaries:
            return TrendAnalysis(
                income_trend=TrendDirection.STABLE,
                income_change_rate=0.0,
                expenditure_trend=TrendDirection.STABLE,
                expenditure_change_rate=0.0,
                loyalty_trend=TrendDirection.STABLE,
                loyalty_change_rate=0.0,
                stability_trend=TrendDirection.STABLE,
                stability_change_rate=0.0,
                risk_level=RiskLevel.MEDIUM,
                risk_factors=[],
                opportunities=[]
            )

        # Use most recent quarterly data
        current_q = quarterly_summaries[0]

        # Determine trends
        income_trend = current_q.income_trend
        expenditure_trend = current_q.expenditure_trend

        # Calculate change rates
        if len(quarterly_summaries) >= 2 and quarterly_summaries[1].avg_income > 0:
            income_change_rate = ((current_q.avg_income - quarterly_summaries[1].avg_income) /
                                 quarterly_summaries[1].avg_income * 100)
        else:
            income_change_rate = 0.0

        if len(quarterly_summaries) >= 2 and quarterly_summaries[1].avg_expenditure > 0:
            expenditure_change_rate = ((current_q.avg_expenditure - quarterly_summaries[1].avg_expenditure) /
                                      quarterly_summaries[1].avg_expenditure * 100)
        else:
            expenditure_change_rate = 0.0

        # Loyalty and stability trends
        if current_q.loyalty_change > 5:
            loyalty_trend = TrendDirection.INCREASING
        elif current_q.loyalty_change < -5:
            loyalty_trend = TrendDirection.DECREASING
        else:
            loyalty_trend = TrendDirection.STABLE

        loyalty_change_rate = current_q.loyalty_change

        if current_q.stability_change > 5:
            stability_trend = TrendDirection.INCREASING
        elif current_q.stability_change < -5:
            stability_trend = TrendDirection.DECREASING
        else:
            stability_trend = TrendDirection.STABLE

        stability_change_rate = current_q.stability_change

        # Risk assessment
        risk_factors = []
        opportunities = []

        if recent_data.loyalty < 40:
            risk_factors.append("Very low loyalty - risk of uprising")
        elif recent_data.loyalty < 50:
            risk_factors.append("Low loyalty - population discontent")

        if recent_data.stability < 40:
            risk_factors.append("Very low stability - chaos potential")

        if recent_data.actual_surplus < 0:
            risk_factors.append("Negative budget - financial crisis")

        if income_trend == TrendDirection.DECREASING:
            risk_factors.append("Declining income trend")

        if loyalty_trend == TrendDirection.DECREASING:
            risk_factors.append("Declining loyalty")

        # Opportunities
        if income_trend == TrendDirection.INCREASING and income_change_rate > 10:
            opportunities.append("Strong income growth supports expansion")

        if loyalty_trend == TrendDirection.INCREASING and loyalty_change_rate > 5:
            opportunities.append("Loyalty improvement enables reforms")

        if recent_data.actual_surplus > 200:
            opportunities.append("Large surplus for investment")

        # Determine overall risk level
        critical_count = sum(1 for f in risk_factors if "very low" in f.lower() or "crisis" in f.lower())
        if critical_count >= 2 or len(risk_factors) >= 4:
            risk_level = RiskLevel.HIGH
        elif len(risk_factors) >= 2:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return TrendAnalysis(
            income_trend=income_trend,
            income_change_rate=income_change_rate,
            expenditure_trend=expenditure_trend,
            expenditure_change_rate=expenditure_change_rate,
            loyalty_trend=loyalty_trend,
            loyalty_change_rate=loyalty_change_rate,
            stability_trend=stability_trend,
            stability_change_rate=stability_change_rate,
            risk_level=risk_level,
            risk_factors=risk_factors,
            opportunities=opportunities
        )

    def _assess_data_quality(
        self,
        recent_data: MonthlyDetailedData,
        quarterly_summaries: List[QuarterlySummary],
        annual_summaries: List[AnnualSummary]
    ) -> tuple:
        """Assess data quality and generate warnings"""
        warnings = []

        if not recent_data or recent_data.month == 0:
            warnings.append("No recent monthly data available")

        if len(quarterly_summaries) < 2:
            warnings.append("Limited quarterly data - trend analysis may be inaccurate")

        if not annual_summaries:
            warnings.append("No annual summaries available")

        # Determine quality level
        if not recent_data or not quarterly_summaries:
            data_quality = "minimal"
        elif len(quarterly_summaries) < 4 or not annual_summaries:
            data_quality = "partial"
        else:
            data_quality = "complete"

        return data_quality, warnings

    # ========== LLM Summary Generation ==========

    async def _generate_quarterly_summary_with_llm(self, data: Dict) -> str:
        """Generate quarterly summary using LLM"""
        prompt = f"""
Generate a one-sentence summary for this quarterly data:

Quarter: Q{data['quarter']} Year {data['year']}
Average Monthly Income: {data['avg_income']:.2f}
Income Change: {data['income_change']:+.1f}%
Loyalty Change: {data['loyalty_change']:+.1f}
Stability Change: {data['stability_change']:+.1f}
Major Events: {', '.join(data['major_events']) if data['major_events'] else 'None'}
Special Events: {', '.join(data['special_event_types']) if data['special_event_types'] else 'None'}

Requirements:
- One sentence maximum
- Focus on key trends and significant changes
- Mention any critical events
- Use concise, professional language
- Be objective and factual

Example output: "Income grew 12.5% while loyalty improved by 5 points, despite a rebellion in June."
"""

        system_prompt = """
You are a provincial affairs officer. Your role is to faithfully integrate province historical data.

Output format: Follow the designed data format.
Style: Concise, accurate, loyal to data.
"""

        summary = await self.call_llm_text(
            prompt=prompt,
            system_prompt=system_prompt
        )

        if not summary:
            return "Quarterly data summarized from provincial records."

        return summary

    async def _generate_annual_summary_with_llm(self, data: Dict) -> str:
        """Generate annual summary using LLM"""
        prompt = f"""
Generate a one-sentence summary for this annual data:

Year: {data['year']}
Total Income: {data['total_income']:.2f}
Average Monthly Income: {data['avg_monthly_income']:.2f}
Total Surplus: {data['total_surplus']:.2f}
Loyalty Change: {data['loyalty_change']:+.1f}
Disasters: {data['disaster_count']}
Rebellions: {data['rebellion_count']}

Requirements:
- One sentence maximum
- Summarize overall performance
- Highlight major achievements or problems
- Mention significant events

Example output: "Year 1 showed good performance with 15% income growth despite one rebellion."
"""

        system_prompt = """
You are a provincial affairs officer. Your role is to faithfully integrate province historical data.

Output format: Follow the designed data format.
Style: Concise, accurate, loyal to data.
"""

        summary = await self.call_llm_text(
            prompt=prompt,
            system_prompt=system_prompt
        )

        if not summary:
            return "Annual data summarized from provincial records."

        return summary

    # ========== Helper Methods ==========

    def _create_default_monthly_data(
        self,
        province: Optional[Dict],
        month: int,
        year: int
    ) -> MonthlyDetailedData:
        """Create default monthly data when no history exists"""
        if province is None:
            province = {}

        return MonthlyDetailedData(
            month=month,
            year=year,
            population=province.get('population', 50000),
            development_level=province.get('development_level', 5.0),
            loyalty=province.get('loyalty', 50.0),
            stability=province.get('stability', 50.0),
            actual_income=0.0,
            actual_expenditure=0.0,
            reported_income=0.0,
            reported_expenditure=0.0,
            actual_surplus=0.0,
            reported_surplus=0.0,
            events=[]
        )
