
from pydantic import BaseModel, Field


# =============================================================================
# Base Output Models
# =============================================================================


class BaseAdvisoryOutput(BaseModel):
    
    # Summary is always present
    summary: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Brief summary of the response",
    )
    
    # Confidence indicator
    confidence_note: str | None = Field(
        default=None,
        description="Any caveats or limitations in the response",
    )


# =============================================================================
# Client-Focused Outputs
# =============================================================================


class ClientSummaryOutput(BaseAdvisoryOutput):
    
    # Client identification
    client_name: str | None = Field(
        default=None,
        description="Name of the client organization",
    )
    industry: str | None = Field(
        default=None,
        description="Client's primary industry",
    )
    
    # Key information
    key_facts: list[str] = Field(
        default_factory=list,
        description="Important facts about the client",
    )
    engagement_history: list[str] = Field(
        default_factory=list,
        description="History of engagements with this client",
    )
    
    # Relationships
    key_contacts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Key contacts at the client organization",
    )
    
    # Strategic context
    strategic_priorities: list[str] = Field(
        default_factory=list,
        description="Client's known strategic priorities",
    )


# =============================================================================
# Risk & Analysis Outputs
# =============================================================================


class RiskItem(BaseModel):
    
    risk: str = Field(..., description="Description of the risk")
    severity: str = Field(
        default="medium",
        description="Severity level: low, medium, high, critical",
    )
    likelihood: str = Field(
        default="possible",
        description="Likelihood: unlikely, possible, likely, certain",
    )
    mitigation: str | None = Field(
        default=None,
        description="Suggested mitigation strategy",
    )
    source: str | None = Field(
        default=None,
        description="Source document for this risk",
    )


class RiskAnalysisOutput(BaseAdvisoryOutput):
    
    # Risk inventory
    risks: list[RiskItem] = Field(
        default_factory=list,
        description="Identified risks with assessment",
    )
    
    # Categorization
    high_priority_risks: list[str] = Field(
        default_factory=list,
        description="Risks requiring immediate attention",
    )
    
    # Aggregate assessment
    overall_risk_level: str = Field(
        default="moderate",
        description="Overall risk assessment: low, moderate, elevated, high",
    )
    
    # Recommendations
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Recommended risk mitigation actions",
    )


class OpportunityItem(BaseModel):
    
    opportunity: str = Field(..., description="Description of the opportunity")
    potential_impact: str = Field(
        default="medium",
        description="Potential impact: low, medium, high, transformative",
    )
    effort_required: str = Field(
        default="medium",
        description="Effort required: low, medium, high",
    )
    timeframe: str | None = Field(
        default=None,
        description="Expected timeframe to realize",
    )


class OpportunityAnalysisOutput(BaseAdvisoryOutput):
    
    opportunities: list[OpportunityItem] = Field(
        default_factory=list,
        description="Identified opportunities",
    )
    
    quick_wins: list[str] = Field(
        default_factory=list,
        description="Low-effort, high-impact opportunities",
    )
    
    strategic_opportunities: list[str] = Field(
        default_factory=list,
        description="Long-term strategic opportunities",
    )


# =============================================================================
# Recommendation Outputs
# =============================================================================


class Recommendation(BaseModel):
    
    recommendation: str = Field(..., description="The recommendation")
    rationale: str = Field(
        default="",
        description="Reasoning behind the recommendation",
    )
    priority: str = Field(
        default="medium",
        description="Priority: low, medium, high",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Other recommendations this depends on",
    )


class RecommendationsOutput(BaseAdvisoryOutput):
    
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Ordered list of recommendations",
    )
    
    # Categorization
    immediate_actions: list[str] = Field(
        default_factory=list,
        description="Actions to take immediately",
    )
    short_term_actions: list[str] = Field(
        default_factory=list,
        description="Actions for the next 30-90 days",
    )
    long_term_actions: list[str] = Field(
        default_factory=list,
        description="Actions for 90+ days",
    )
    
    # Context
    assumptions: list[str] = Field(
        default_factory=list,
        description="Key assumptions underlying recommendations",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints considered in recommendations",
    )


class ActionItem(BaseModel):
    
    action: str = Field(..., description="The action to take")
    owner: str | None = Field(default=None, description="Responsible party")
    due_date: str | None = Field(default=None, description="Target completion date")
    priority: str = Field(default="medium", description="Priority level")
    status: str = Field(default="not_started", description="Current status")


class ActionItemsOutput(BaseAdvisoryOutput):
    
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Extracted action items",
    )
    
    # Grouping
    by_owner: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Actions grouped by owner",
    )
    by_priority: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Actions grouped by priority",
    )


# =============================================================================
# Executive Communication Outputs
# =============================================================================


class ExecutiveSummaryOutput(BaseAdvisoryOutput):
    
    # One-liner
    headline: str = Field(
        ...,
        max_length=200,
        description="Single sentence capturing the key point",
    )
    
    # Key points (3-5 bullets)
    key_points: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=5,
        description="Most important points (3-5 items)",
    )
    
    # Decision required
    decision_required: str | None = Field(
        default=None,
        description="Decision or action needed from executive",
    )
    
    # Background
    context: str = Field(
        default="",
        description="Brief background context",
    )
    
    # Next steps
    next_steps: list[str] = Field(
        default_factory=list,
        description="Recommended next steps",
    )


class TalkingPoint(BaseModel):
    
    point: str = Field(..., description="The talking point")
    supporting_data: str | None = Field(
        default=None,
        description="Data or evidence supporting this point",
    )
    anticipated_questions: list[str] = Field(
        default_factory=list,
        description="Questions this point might raise",
    )


class TalkingPointsOutput(BaseAdvisoryOutput):
    
    talking_points: list[TalkingPoint] = Field(
        default_factory=list,
        description="Ordered talking points",
    )
    
    # Audience context
    target_audience: str | None = Field(
        default=None,
        description="Intended audience for these points",
    )
    
    # Key messages
    key_messages: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Core messages to convey (max 3)",
    )
    
    # Q&A preparation
    potential_objections: list[str] = Field(
        default_factory=list,
        description="Potential objections to prepare for",
    )
    supporting_facts: list[str] = Field(
        default_factory=list,
        description="Key facts to reference",
    )


# =============================================================================
# Comparison & Research Outputs
# =============================================================================


class ComparisonItem(BaseModel):
    
    option: str = Field(..., description="Name of the option")
    pros: list[str] = Field(default_factory=list, description="Advantages")
    cons: list[str] = Field(default_factory=list, description="Disadvantages")
    best_for: str | None = Field(
        default=None,
        description="Scenarios where this option is best",
    )


class CompareApproachesOutput(BaseAdvisoryOutput):
    
    approaches: list[ComparisonItem] = Field(
        default_factory=list,
        description="Approaches being compared",
    )
    
    recommendation: str = Field(
        default="",
        description="Recommended approach based on comparison",
    )
    
    criteria_used: list[str] = Field(
        default_factory=list,
        description="Criteria used for comparison",
    )


class ResearchTopicOutput(BaseAdvisoryOutput):
    
    # Core findings
    key_findings: list[str] = Field(
        default_factory=list,
        description="Key findings from research",
    )
    
    # Detail
    detailed_analysis: str = Field(
        default="",
        description="Detailed analysis of the topic",
    )
    
    # Context
    background: str = Field(
        default="",
        description="Background context on the topic",
    )
    
    # References
    key_sources: list[str] = Field(
        default_factory=list,
        description="Key sources referenced",
    )
    
    # Gaps
    information_gaps: list[str] = Field(
        default_factory=list,
        description="Information that could not be found",
    )


# =============================================================================
# General Q&A Output
# =============================================================================


class QuestionAnswerOutput(BaseAdvisoryOutput):
    
    # Direct answer
    answer: str = Field(
        ...,
        description="Direct answer to the question",
    )
    
    # Supporting information
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting the answer",
    )
    
    # Related topics
    related_topics: list[str] = Field(
        default_factory=list,
        description="Related topics the user might want to explore",
    )
    
    # Follow-up suggestions
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions",
    )


# =============================================================================
# Output Type Mapping
# =============================================================================

# Map task types to their output models
TASK_OUTPUT_MODELS = {
    "question_answer": QuestionAnswerOutput,
    "summarize_client": ClientSummaryOutput,
    "client_background": ClientSummaryOutput,
    "risk_analysis": RiskAnalysisOutput,
    "opportunity_analysis": OpportunityAnalysisOutput,
    "draft_recommendations": RecommendationsOutput,
    "action_items": ActionItemsOutput,
    "executive_summary": ExecutiveSummaryOutput,
    "talking_points": TalkingPointsOutput,
    "compare_approaches": CompareApproachesOutput,
    "research_topic": ResearchTopicOutput,
}


def get_output_model(task_type: str) -> type[BaseAdvisoryOutput]:
    return TASK_OUTPUT_MODELS.get(task_type, QuestionAnswerOutput)
