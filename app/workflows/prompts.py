
from string import Template
from typing import Any

from app.models.queries import TaskType

# =============================================================================
# Base System Prompts
# =============================================================================

BASE_SYSTEM_PROMPT = """You are an internal AI assistant for a professional advisory firm.
Your role is to help consultants, analysts, and partners by providing accurate, 
well-structured insights based on internal knowledge and documents.

Guidelines:
- Be precise and professional in your responses
- Always cite sources when making factual claims
- Acknowledge uncertainty when information is incomplete
- Provide actionable insights, not just summaries
- Use clear, business-appropriate language

Current user role: {user_role}
"""

STRUCTURED_OUTPUT_INSTRUCTION = """
Your response MUST be valid JSON matching this schema:
{schema}

Do not include any text outside the JSON object.
Do not wrap the JSON in markdown code blocks.
Ensure all string values are properly escaped.
"""

# =============================================================================
# Task-Specific Templates
# =============================================================================

TEMPLATES: dict[TaskType, dict[str, str]] = {
    TaskType.QUESTION_ANSWER: {
        "system": BASE_SYSTEM_PROMPT + """
You are answering a general question using the provided context.
Be direct and concise while remaining thorough.
""",
        "user": """Based on the following internal documents, please answer this question:

QUESTION: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Brief summary of your answer",
    "answer": "Detailed answer to the question",
    "supporting_evidence": ["Evidence point 1", "Evidence point 2"],
    "related_topics": ["Related topic 1", "Related topic 2"],
    "follow_up_questions": ["Suggested follow-up 1", "Suggested follow-up 2"],
    "confidence_note": "Any caveats or limitations"
}}
""",
    },
    
    TaskType.SUMMARIZE_CLIENT: {
        "system": BASE_SYSTEM_PROMPT + """
You are creating a client summary for internal reference.
Focus on key facts, history, and strategic context.
""",
        "user": """Based on the following internal documents, create a comprehensive client summary:

CLIENT FILTER: {client_name}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Executive summary of the client",
    "client_name": "Client organization name",
    "industry": "Primary industry",
    "key_facts": ["Important fact 1", "Important fact 2"],
    "engagement_history": ["Engagement 1", "Engagement 2"],
    "key_contacts": [{{"name": "Contact Name", "role": "Role", "notes": "Any notes"}}],
    "strategic_priorities": ["Priority 1", "Priority 2"],
    "confidence_note": "Any gaps in available information"
}}
""",
    },
    
    TaskType.RISK_ANALYSIS: {
        "system": BASE_SYSTEM_PROMPT + """
You are conducting a risk analysis for an advisory engagement.
Be thorough in identifying risks across all dimensions:
- Strategic risks
- Operational risks
- Financial risks
- Regulatory/compliance risks
- Reputational risks

Prioritize risks by severity and likelihood.
""",
        "user": """Based on the following internal documents, perform a comprehensive risk analysis:

FOCUS AREA: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Executive summary of the risk landscape",
    "risks": [
        {{
            "risk": "Description of the risk",
            "severity": "low|medium|high|critical",
            "likelihood": "unlikely|possible|likely|certain",
            "mitigation": "Suggested mitigation approach",
            "source": "Source document reference"
        }}
    ],
    "high_priority_risks": ["Risk requiring immediate attention 1"],
    "overall_risk_level": "low|moderate|elevated|high",
    "recommended_actions": ["Action 1", "Action 2"],
    "confidence_note": "Any limitations in the analysis"
}}
""",
    },
    
    TaskType.DRAFT_RECOMMENDATIONS: {
        "system": BASE_SYSTEM_PROMPT + """
You are drafting recommendations for a client or internal initiative.
Recommendations should be:
- Specific and actionable
- Prioritized by impact and feasibility
- Supported by evidence from the context
- Realistic given constraints
""",
        "user": """Based on the following internal documents, draft recommendations:

FOCUS: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Overview of recommendations",
    "recommendations": [
        {{
            "recommendation": "Specific recommendation",
            "rationale": "Why this is recommended",
            "priority": "low|medium|high",
            "dependencies": ["Any prerequisites"]
        }}
    ],
    "immediate_actions": ["Action for next 7 days"],
    "short_term_actions": ["Action for next 30-90 days"],
    "long_term_actions": ["Action for 90+ days"],
    "assumptions": ["Key assumption 1"],
    "constraints": ["Known constraint 1"],
    "confidence_note": "Any caveats"
}}
""",
    },
    
    TaskType.EXECUTIVE_SUMMARY: {
        "system": BASE_SYSTEM_PROMPT + """
You are creating an executive summary for senior leadership.
Be extremely concise - executives have limited time.
Focus on:
- One clear headline/takeaway
- 3-5 key points maximum
- Clear ask or decision needed
- Next steps
""",
        "user": """Create an executive summary based on the following:

TOPIC: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "One paragraph executive overview",
    "headline": "Single sentence capturing the key point (max 200 chars)",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "decision_required": "Decision or action needed from executive (if any)",
    "context": "Brief background",
    "next_steps": ["Next step 1", "Next step 2"],
    "confidence_note": "Any limitations"
}}
""",
    },
    
    TaskType.TALKING_POINTS: {
        "system": BASE_SYSTEM_PROMPT + """
You are preparing talking points for a meeting or presentation.
Talking points should be:
- Clear and memorable
- Supported by data where possible
- Anticipate likely questions
- Build a coherent narrative
""",
        "user": """Prepare talking points for the following:

CONTEXT/MEETING: {query}

BACKGROUND:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Overview of the talking points",
    "talking_points": [
        {{
            "point": "The talking point",
            "supporting_data": "Evidence or data to support",
            "anticipated_questions": ["Question this might raise"]
        }}
    ],
    "target_audience": "Who these points are for",
    "key_messages": ["Core message 1", "Core message 2"],
    "potential_objections": ["Objection to prepare for"],
    "supporting_facts": ["Key fact to reference"],
    "confidence_note": "Any limitations"
}}
""",
    },
    
    TaskType.ACTION_ITEMS: {
        "system": BASE_SYSTEM_PROMPT + """
You are extracting action items from documents or discussions.
Action items should be:
- Specific and measurable
- Have clear ownership (if identifiable)
- Have realistic timeframes
- Prioritized appropriately
""",
        "user": """Extract action items from the following:

FOCUS: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Overview of action items",
    "action_items": [
        {{
            "action": "Specific action to take",
            "owner": "Responsible party (if identifiable)",
            "due_date": "Target date (if mentioned)",
            "priority": "low|medium|high",
            "status": "not_started"
        }}
    ],
    "by_owner": {{"Owner Name": ["Action 1"]}},
    "by_priority": {{"high": ["Action 1"], "medium": ["Action 2"]}},
    "confidence_note": "Any limitations"
}}
""",
    },
    
    TaskType.COMPARE_APPROACHES: {
        "system": BASE_SYSTEM_PROMPT + """
You are comparing different approaches, options, or alternatives.
Provide balanced analysis:
- Clear criteria for comparison
- Honest pros and cons
- Context-appropriate recommendation
""",
        "user": """Compare the following approaches/options:

COMPARISON REQUEST: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Overview of the comparison",
    "approaches": [
        {{
            "option": "Name of option",
            "pros": ["Advantage 1"],
            "cons": ["Disadvantage 1"],
            "best_for": "Scenario where this option excels"
        }}
    ],
    "recommendation": "Recommended approach with rationale",
    "criteria_used": ["Criterion 1", "Criterion 2"],
    "confidence_note": "Any limitations"
}}
""",
    },
    
    TaskType.RESEARCH_TOPIC: {
        "system": BASE_SYSTEM_PROMPT + """
You are researching a topic using internal knowledge sources.
Provide comprehensive coverage:
- Key findings and facts
- Background context
- Identify information gaps
""",
        "user": """Research the following topic:

TOPIC: {query}

AVAILABLE SOURCES:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Executive summary of findings",
    "key_findings": ["Finding 1", "Finding 2"],
    "detailed_analysis": "Detailed analysis of the topic",
    "background": "Background context",
    "key_sources": ["Source 1 reference", "Source 2 reference"],
    "information_gaps": ["Information we couldn't find"],
    "confidence_note": "Limitations and confidence level"
}}
""",
    },
    
    TaskType.OPPORTUNITY_ANALYSIS: {
        "system": BASE_SYSTEM_PROMPT + """
You are identifying opportunities for growth, improvement, or strategic advantage.
Focus on:
- Quick wins (low effort, high impact)
- Strategic opportunities (longer term)
- Realistic assessment of potential
""",
        "user": """Identify opportunities based on:

FOCUS: {query}

CONTEXT:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Overview of opportunities identified",
    "opportunities": [
        {{
            "opportunity": "Description",
            "potential_impact": "low|medium|high|transformative",
            "effort_required": "low|medium|high",
            "timeframe": "Expected timeframe"
        }}
    ],
    "quick_wins": ["Low-effort, high-impact opportunity"],
    "strategic_opportunities": ["Long-term strategic opportunity"],
    "confidence_note": "Any limitations"
}}
""",
    },
    
    TaskType.CLIENT_BACKGROUND: {
        "system": BASE_SYSTEM_PROMPT + """
You are providing client background information for engagement preparation.
Include historical context and relationship details.
""",
        "user": """Provide client background information:

CLIENT: {query}

AVAILABLE INFORMATION:
{context}

Provide your response in the following JSON format:
{{
    "summary": "Client background overview",
    "client_name": "Client name",
    "industry": "Industry",
    "key_facts": ["Fact 1", "Fact 2"],
    "engagement_history": ["Past engagement 1"],
    "key_contacts": [{{"name": "Name", "role": "Role", "notes": "Notes"}}],
    "strategic_priorities": ["Priority 1"],
    "confidence_note": "Information gaps"
}}
""",
    },
}


class PromptBuilder:
    
    def build(
        self,
        task_type: TaskType,
        query: str,
        context: str,
        user_role: str = "analyst",
        client_name: str | None = None,
        additional_vars: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        template = TEMPLATES.get(task_type, TEMPLATES[TaskType.QUESTION_ANSWER])
        
        # Build variable dict
        variables = {
            "query": query,
            "context": context,
            "user_role": user_role,
            "client_name": client_name or "Not specified",
        }
        
        if additional_vars:
            variables.update(additional_vars)
        
        # Format prompts
        system_prompt = template["system"].format(**variables)
        user_prompt = template["user"].format(**variables)
        
        return system_prompt, user_prompt
    
    def get_schema_for_task(self, task_type: TaskType) -> dict[str, Any]:
        from app.models.outputs import get_output_model
        
        model = get_output_model(task_type.value)
        return model.model_json_schema()


# Singleton instance
_prompt_builder: PromptBuilder | None = None


def get_prompt_builder() -> PromptBuilder:
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
