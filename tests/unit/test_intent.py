"""
Tests for Intent Detection
"""

import pytest

from app.workflows.intent import IntentDetector, detect_intent_sync, IntentMatch
from app.models.queries import TaskType


@pytest.fixture
def detector():
    """Create an intent detector without LLM fallback."""
    return IntentDetector(llm_service=None)


class TestIntentDetection:
    """Tests for intent detection rules."""
    
    @pytest.mark.parametrize("query,expected_type", [
        # Risk analysis queries
        ("What are the key risks for this project?", TaskType.RISK_ANALYSIS),
        ("Identify the risks in this engagement", TaskType.RISK_ANALYSIS),
        ("Risk analysis for the merger", TaskType.RISK_ANALYSIS),
        ("What potential issues should we consider?", TaskType.RISK_ANALYSIS),
        
        # Summarize client queries
        ("Summarize the client background", TaskType.SUMMARIZE_CLIENT),
        ("Give me a client summary", TaskType.SUMMARIZE_CLIENT),
        ("Client overview for Acme Corp", TaskType.SUMMARIZE_CLIENT),
        
        # Recommendations queries
        ("What do you recommend?", TaskType.DRAFT_RECOMMENDATIONS),
        ("Draft recommendations for the board", TaskType.DRAFT_RECOMMENDATIONS),
        ("What should we suggest to the client?", TaskType.DRAFT_RECOMMENDATIONS),
        
        # Executive summary queries
        ("Create an executive summary", TaskType.EXECUTIVE_SUMMARY),
        ("Executive briefing for the CEO", TaskType.EXECUTIVE_SUMMARY),
        ("High-level overview for leadership", TaskType.EXECUTIVE_SUMMARY),
        
        # Talking points queries
        ("Prepare talking points for the meeting", TaskType.TALKING_POINTS),
        ("What should I say in the presentation?", TaskType.TALKING_POINTS),
        ("Key messages for the board", TaskType.TALKING_POINTS),
        
        # Action items queries
        ("What are the action items?", TaskType.ACTION_ITEMS),
        ("List the next steps", TaskType.ACTION_ITEMS),
        ("Extract to-do items from the notes", TaskType.ACTION_ITEMS),
        
        # Compare approaches queries
        ("Compare the two options", TaskType.COMPARE_APPROACHES),
        ("What are the pros and cons?", TaskType.COMPARE_APPROACHES),
        ("Which approach is better?", TaskType.COMPARE_APPROACHES),
    ])
    def test_rule_based_detection(self, query, expected_type):
        """Test that common queries are detected correctly."""
        result = detect_intent_sync(query)
        assert result.task_type == expected_type
        assert result.method == "rule"
    
    def test_general_question_fallback(self):
        """Ambiguous queries should fall back to Q&A."""
        result = detect_intent_sync("What is the meaning of this document?")
        # Should default to Q&A or at least have lower confidence
        assert result.task_type in [TaskType.QUESTION_ANSWER, TaskType.RESEARCH_TOPIC]
    
    def test_confidence_scoring(self):
        """Clear intent should have higher confidence than ambiguous."""
        clear_result = detect_intent_sync("Perform a risk analysis")
        ambiguous_result = detect_intent_sync("Help me with this")
        
        assert clear_result.confidence > ambiguous_result.confidence
    
    def test_matched_patterns_populated(self):
        """Matched patterns should be tracked for explainability."""
        result = detect_intent_sync("What are the risks in this deal?")
        assert len(result.matched_patterns) > 0


class TestIntentMatch:
    """Tests for IntentMatch dataclass."""
    
    def test_intent_match_creation(self):
        """IntentMatch should store all required fields."""
        match = IntentMatch(
            task_type=TaskType.RISK_ANALYSIS,
            confidence=0.9,
            matched_patterns=["risk.*analysis"],
            method="rule",
        )
        
        assert match.task_type == TaskType.RISK_ANALYSIS
        assert match.confidence == 0.9
        assert len(match.matched_patterns) == 1
        assert match.method == "rule"


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    def test_empty_query(self):
        """Empty query should still return a result."""
        result = detect_intent_sync("")
        assert result is not None
        assert result.task_type == TaskType.QUESTION_ANSWER
    
    def test_very_long_query(self):
        """Long queries should be handled."""
        long_query = "Please analyze the risks in this situation " * 100
        result = detect_intent_sync(long_query)
        assert result is not None
    
    def test_special_characters(self):
        """Queries with special characters should be handled."""
        result = detect_intent_sync("What are the risks? #important @urgent!")
        assert result is not None
    
    def test_case_insensitivity(self):
        """Intent detection should be case-insensitive."""
        lower_result = detect_intent_sync("risk analysis")
        upper_result = detect_intent_sync("RISK ANALYSIS")
        mixed_result = detect_intent_sync("Risk Analysis")
        
        assert lower_result.task_type == upper_result.task_type == mixed_result.task_type
