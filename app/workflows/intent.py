
import re
from dataclasses import dataclass
from typing import Callable

from app.core.config import settings
from app.core.logging import get_logger
from app.models.queries import TaskType

logger = get_logger(__name__)


@dataclass
class IntentMatch:
    
    task_type: TaskType
    confidence: float
    matched_patterns: list[str]
    method: str  # "rule" or "llm"


# Pattern definitions for each task type
# Format: (compiled_regex, weight)
# Higher weights indicate stronger signals
INTENT_PATTERNS: dict[TaskType, list[tuple[re.Pattern, float]]] = {
    TaskType.SUMMARIZE_CLIENT: [
        (re.compile(r"\bsummar(y|ize|ise)\b.*\bclient\b", re.I), 1.0),
        (re.compile(r"\bclient\b.*\bsummar(y|ize|ise)\b", re.I), 1.0),
        (re.compile(r"\bclient\s+(background|overview|profile)\b", re.I), 0.9),
        (re.compile(r"\btell\s+me\s+about\b.*\bclient\b", re.I), 0.8),
        (re.compile(r"\bwho\s+is\b.*\bclient\b", re.I), 0.7),
    ],
    TaskType.CLIENT_BACKGROUND: [
        (re.compile(r"\bbackground\b.*\bclient\b", re.I), 1.0),
        (re.compile(r"\bclient\b.*\bhistory\b", re.I), 0.9),
        (re.compile(r"\bprevious\s+engagements?\b", re.I), 0.8),
    ],
    TaskType.RISK_ANALYSIS: [
        (re.compile(r"\brisk\s+(analysis|assessment|evaluation)\b", re.I), 1.0),
        (re.compile(r"\bidentify\b.*\brisks?\b", re.I), 1.0),
        (re.compile(r"\bwhat\s+are\s+the\s+risks?\b", re.I), 0.9),
        (re.compile(r"\brisk\s+factors?\b", re.I), 0.8),
        (re.compile(r"\bpotential\s+(issues?|problems?|risks?)\b", re.I), 0.7),
    ],
    TaskType.OPPORTUNITY_ANALYSIS: [
        (re.compile(r"\bopportunit(y|ies)\s+analysis\b", re.I), 1.0),
        (re.compile(r"\bidentify\b.*\bopportunit(y|ies)\b", re.I), 1.0),
        (re.compile(r"\bgrowth\s+opportunit(y|ies)\b", re.I), 0.9),
        (re.compile(r"\bpotential\s+opportunit(y|ies)\b", re.I), 0.8),
    ],
    TaskType.DRAFT_RECOMMENDATIONS: [
        (re.compile(r"\b(draft|write|create)\b.*\brecommendations?\b", re.I), 1.0),
        (re.compile(r"\brecommend(ation)?s?\b.*\b(for|to)\b", re.I), 0.9),
        (re.compile(r"\bwhat\s+(do\s+you|should\s+(we|I))\s+recommend\b", re.I), 0.9),
        (re.compile(r"\bsuggestions?\b.*\bfor\b", re.I), 0.7),
        (re.compile(r"\bwhat\s+should\s+(we|they|I)\s+do\b", re.I), 0.7),
    ],
    TaskType.ACTION_ITEMS: [
        (re.compile(r"\baction\s+items?\b", re.I), 1.0),
        (re.compile(r"\bnext\s+steps?\b", re.I), 0.9),
        (re.compile(r"\bto-?do\s+(list|items?)\b", re.I), 0.9),
        (re.compile(r"\btasks?\s+to\s+(complete|do)\b", re.I), 0.8),
        (re.compile(r"\bwhat\s+(needs|has)\s+to\s+be\s+done\b", re.I), 0.7),
    ],
    TaskType.EXECUTIVE_SUMMARY: [
        (re.compile(r"\bexecutive\s+summar(y|ize|ise)\b", re.I), 1.0),
        (re.compile(r"\bbriefing\b", re.I), 0.8),
        (re.compile(r"\bhigh[- ]?level\s+(overview|summary)\b", re.I), 0.8),
        (re.compile(r"\bboard\s+(summary|briefing)\b", re.I), 0.9),
    ],
    TaskType.TALKING_POINTS: [
        (re.compile(r"\btalking\s+points?\b", re.I), 1.0),
        (re.compile(r"\bkey\s+(messages?|points?)\b", re.I), 0.8),
        (re.compile(r"\bprepare\s+(me\s+)?for\s+(a\s+)?(meeting|call|presentation)\b", re.I), 0.8),
        (re.compile(r"\bwhat\s+should\s+I\s+say\b", re.I), 0.7),
    ],
    TaskType.COMPARE_APPROACHES: [
        (re.compile(r"\bcompare\b.*\b(approaches?|options?|alternatives?)\b", re.I), 1.0),
        (re.compile(r"\b(pros?\s+and\s+cons?|advantages?\s+and\s+disadvantages?)\b", re.I), 0.9),
        (re.compile(r"\bwhich\s+(is|option|approach)\s+(better|best)\b", re.I), 0.8),
        (re.compile(r"\bdifference\s+between\b", re.I), 0.7),
    ],
    TaskType.RESEARCH_TOPIC: [
        (re.compile(r"\bresearch\b.*\btopic\b", re.I), 1.0),
        (re.compile(r"\bwhat\s+(do\s+we|does\s+the)\s+know\s+about\b", re.I), 0.8),
        (re.compile(r"\bfind\s+(information|details?)\s+(on|about)\b", re.I), 0.8),
        (re.compile(r"\blook\s+up\b", re.I), 0.6),
    ],
    TaskType.QUESTION_ANSWER: [
        # This is the fallback - lower weights
        (re.compile(r"^\s*(what|who|when|where|why|how)\b", re.I), 0.3),
        (re.compile(r"\?$"), 0.2),
    ],
}

# Confidence thresholds
RULE_CONFIDENCE_THRESHOLD = 0.6
LLM_FALLBACK_THRESHOLD = 0.4


class IntentDetector:
    
    def __init__(self, llm_service=None) -> None:
        self.llm_service = llm_service
    
    async def detect(
        self,
        query: str,
        use_llm_fallback: bool = True,
    ) -> IntentMatch:
        if not settings.feature_intent_detection_enabled:
            return IntentMatch(
                task_type=TaskType.QUESTION_ANSWER,
                confidence=1.0,
                matched_patterns=[],
                method="disabled",
            )
        
        # Try rule-based detection first
        rule_result = self._detect_with_rules(query)
        
        logger.debug(
            "Rule-based detection result",
            task_type=rule_result.task_type.value,
            confidence=rule_result.confidence,
            patterns=rule_result.matched_patterns,
        )
        
        # If confident enough, use rule result
        if rule_result.confidence >= RULE_CONFIDENCE_THRESHOLD:
            return rule_result
        
        # Try LLM fallback if enabled and rules weren't confident
        if use_llm_fallback and self.llm_service and rule_result.confidence < LLM_FALLBACK_THRESHOLD:
            try:
                llm_result = await self._detect_with_llm(query)
                if llm_result.confidence > rule_result.confidence:
                    return llm_result
            except Exception as e:
                logger.warning(
                    "LLM intent detection failed, using rule result",
                    error=str(e),
                )
        
        return rule_result
    
    def _detect_with_rules(self, query: str) -> IntentMatch:
        scores: dict[TaskType, tuple[float, list[str]]] = {}
        
        for task_type, patterns in INTENT_PATTERNS.items():
            matched = []
            max_weight = 0.0
            
            for pattern, weight in patterns:
                if pattern.search(query):
                    matched.append(pattern.pattern)
                    max_weight = max(max_weight, weight)
            
            if matched:
                scores[task_type] = (max_weight, matched)
        
        if not scores:
            # Default to Q&A
            return IntentMatch(
                task_type=TaskType.QUESTION_ANSWER,
                confidence=0.3,
                matched_patterns=[],
                method="rule",
            )
        
        # Get highest scoring task
        best_task = max(scores.keys(), key=lambda t: scores[t][0])
        best_score, matched_patterns = scores[best_task]
        
        return IntentMatch(
            task_type=best_task,
            confidence=best_score,
            matched_patterns=matched_patterns,
            method="rule",
        )
    
    async def _detect_with_llm(self, query: str) -> IntentMatch:
        # Build task type descriptions
        task_descriptions = {
            TaskType.SUMMARIZE_CLIENT: "Summarize client background or profile",
            TaskType.RISK_ANALYSIS: "Identify and analyze risks",
            TaskType.OPPORTUNITY_ANALYSIS: "Identify opportunities or growth areas",
            TaskType.DRAFT_RECOMMENDATIONS: "Create recommendations or suggestions",
            TaskType.ACTION_ITEMS: "Extract action items or next steps",
            TaskType.EXECUTIVE_SUMMARY: "Create high-level executive briefing",
            TaskType.TALKING_POINTS: "Prepare talking points for meetings",
            TaskType.COMPARE_APPROACHES: "Compare different options or approaches",
            TaskType.RESEARCH_TOPIC: "Research a specific topic",
            TaskType.QUESTION_ANSWER: "Answer a general question",
        }
        
        task_list = "\n".join(
            f"- {task.value}: {desc}"
            for task, desc in task_descriptions.items()
        )
        
        prompt = f"""Classify the following query into one of these task types:

{task_list}

Query: {query}

Respond with just the task type value (e.g., "risk_analysis") and a confidence score from 0 to 1.
Format: task_type|confidence

Example response: risk_analysis|0.9
"""
        
        response = await self.llm_service.generate(
            prompt=prompt,
            max_tokens=50,
            temperature=0,
        )
        
        # Parse response
        try:
            parts = response.strip().split("|")
            task_value = parts[0].strip()
            confidence = float(parts[1].strip()) if len(parts) > 1 else 0.7
            
            task_type = TaskType(task_value)
            
            return IntentMatch(
                task_type=task_type,
                confidence=confidence,
                matched_patterns=[],
                method="llm",
            )
        except (ValueError, IndexError) as e:
            logger.warning(
                "Failed to parse LLM intent response",
                response=response,
                error=str(e),
            )
            raise


def detect_intent_sync(query: str) -> IntentMatch:
    detector = IntentDetector()
    return detector._detect_with_rules(query)
