#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

# Sample document templates
SAMPLE_DOCUMENTS = [
    {
        "filename": "risk_management_playbook.md",
        "type": "playbook",
        "content": """# Risk Management Playbook

## Overview

This playbook provides guidelines for identifying, assessing, and mitigating risks in client engagements.

## Risk Categories

### Strategic Risks
- Market changes affecting client's competitive position
- Technology disruption in client's industry
- Regulatory changes impacting business model

### Operational Risks
- Process inefficiencies
- Supply chain vulnerabilities
- Technology system failures

### Financial Risks
- Cash flow constraints
- Credit exposure
- Foreign exchange fluctuations

### Compliance Risks
- Regulatory non-compliance
- Data privacy violations
- Environmental regulations

## Risk Assessment Framework

### Likelihood Scale
1. **Rare** - May occur only in exceptional circumstances
2. **Unlikely** - Could occur at some time
3. **Possible** - Might occur at some time
4. **Likely** - Will probably occur
5. **Almost Certain** - Expected to occur

### Impact Scale
1. **Insignificant** - Minimal impact on objectives
2. **Minor** - Some impact, easily managed
3. **Moderate** - Significant impact, requires management attention
4. **Major** - Serious impact on objectives
5. **Catastrophic** - Critical impact, threatens viability

## Mitigation Strategies

### Risk Avoidance
Eliminate activities that generate risk when the risk outweighs potential benefits.

### Risk Reduction
Implement controls to reduce likelihood or impact.

### Risk Transfer
Transfer risk through insurance, contracts, or partnerships.

### Risk Acceptance
Accept residual risk when mitigation costs exceed potential impact.

## Documentation Requirements

All risk assessments must include:
- Risk description
- Likelihood and impact scores
- Current controls
- Recommended mitigations
- Risk owner
- Review timeline
"""
    },
    {
        "filename": "client_engagement_guidelines.md",
        "type": "guideline",
        "content": """# Client Engagement Guidelines

## Introduction

These guidelines establish standards for professional client engagements.

## Pre-Engagement

### Opportunity Assessment
- Evaluate strategic fit
- Assess team capability
- Review conflict checks
- Estimate resource requirements

### Proposal Development
- Clear scope definition
- Realistic timeline
- Transparent pricing
- Risk allocation

## During Engagement

### Communication Standards
- Weekly status updates
- Monthly executive briefings
- Immediate escalation of critical issues

### Quality Assurance
- Peer review of deliverables
- Partner sign-off on key milestones
- Client feedback integration

### Documentation
- Maintain complete engagement files
- Document key decisions
- Track scope changes

## Post-Engagement

### Knowledge Capture
- Document lessons learned
- Update playbooks
- Share best practices

### Relationship Management
- Client satisfaction survey
- Follow-up opportunities
- Referral requests
"""
    },
    {
        "filename": "acme_corp_client_summary.md",
        "type": "client_summary",
        "content": """# Client Summary: Acme Corporation

## Company Overview

**Industry:** Manufacturing
**Headquarters:** Chicago, IL
**Revenue:** $2.4B (FY2023)
**Employees:** 8,500

## Key Contacts

| Name | Role | Notes |
|------|------|-------|
| John Smith | CEO | Decision maker, prefers data-driven presentations |
| Sarah Johnson | CFO | Primary commercial contact |
| Mike Chen | COO | Focus on operational efficiency |

## Engagement History

### 2023 - Digital Transformation Assessment
- Scope: Evaluate technology modernization opportunities
- Duration: 12 weeks
- Fee: $450K
- Outcome: Recommendations adopted, led to follow-on work

### 2022 - Supply Chain Optimization
- Scope: Reduce costs and improve resilience
- Duration: 8 weeks
- Fee: $280K
- Outcome: 12% cost reduction achieved

## Strategic Priorities (2024)

1. International expansion into European markets
2. Sustainability initiatives and ESG reporting
3. Workforce automation and AI adoption
4. Supply chain diversification

## Relationship Notes

- Annual planning meeting typically in November
- CEO is alumni of partner firm - maintain relationship
- Competitive situation with McKinsey on technology work
"""
    },
    {
        "filename": "due_diligence_checklist.md",
        "type": "template",
        "content": """# Due Diligence Checklist

## Financial Review

- [ ] Historical financial statements (3 years)
- [ ] Revenue breakdown by product/geography
- [ ] Customer concentration analysis
- [ ] Working capital trends
- [ ] Debt and obligations schedule
- [ ] Tax compliance status

## Operational Review

- [ ] Organization structure
- [ ] Key employee identification
- [ ] Technology systems inventory
- [ ] Vendor and supplier contracts
- [ ] Real estate and facilities
- [ ] Insurance coverage

## Legal Review

- [ ] Corporate documents
- [ ] Material contracts
- [ ] Intellectual property
- [ ] Litigation history
- [ ] Regulatory compliance
- [ ] Environmental liabilities

## Commercial Review

- [ ] Market position analysis
- [ ] Competitive landscape
- [ ] Customer satisfaction
- [ ] Sales pipeline
- [ ] Pricing strategy
- [ ] Growth opportunities

## Integration Considerations

- [ ] Cultural assessment
- [ ] Synergy identification
- [ ] Integration complexity
- [ ] Key person retention
- [ ] System compatibility
- [ ] Change management needs
"""
    },
    {
        "filename": "partner_memo_q4_strategy.md",
        "type": "partner_memo",
        "content": """# Partner Memo: Q4 2024 Strategy Update

**Classification: Partner-Only**
**Date: October 2024**

## Executive Summary

Q4 presents significant growth opportunities. We are targeting 15% YoY revenue growth while maintaining profitability margins.

## Priority Initiatives

### 1. AI Advisory Practice Launch
- Target: $10M pipeline by year-end
- Team: 8 dedicated consultants
- Go-to-market: Industry events, thought leadership

### 2. Private Equity Expansion
- 3 new PE relationship targets identified
- Focus on portfolio company transformation
- Expected deal flow: 12-15 opportunities

### 3. Partner Recruiting
- 2 lateral partners targeted
- Industry focus: Healthcare, Technology
- Timeline: Offers by November 30

## Financial Targets

| Metric | Target | Current |
|--------|--------|---------|
| Revenue | $45M | $38M |
| Utilization | 72% | 68% |
| Realization | 94% | 91% |
| New Clients | 8 | 5 |

## Resource Allocation

Partner time allocation guidance:
- 60% billable work
- 20% business development
- 10% practice building
- 10% firm initiatives

## Key Dates

- October 15: Q4 planning session
- November 1: Partner retreat
- December 10: Year-end review
- December 20: Holiday party
"""
    },
    {
        "filename": "fee_structure_2024.md",
        "type": "fee_structure",
        "content": """# Standard Fee Structure 2024

**Classification: Partner-Only**
**Effective: January 1, 2024**

## Hourly Rates

| Level | Standard Rate | Premium Rate |
|-------|---------------|--------------|
| Partner | $850 | $1,100 |
| Senior Manager | $650 | $800 |
| Manager | $500 | $650 |
| Senior Consultant | $400 | $500 |
| Consultant | $325 | $400 |
| Analyst | $250 | $325 |

## Project-Based Pricing

### Strategy Engagements
- Market Assessment: $150K - $300K
- Growth Strategy: $200K - $400K
- M&A Strategy: $250K - $500K

### Operations Engagements
- Process Improvement: $100K - $250K
- Supply Chain: $150K - $350K
- Digital Transformation: $300K - $750K

### Due Diligence
- Commercial DD: $150K - $300K
- Operational DD: $200K - $400K
- Full-scope DD: $350K - $700K

## Discount Guidelines

| Scenario | Maximum Discount |
|----------|-----------------|
| Strategic client | 15% |
| Large engagement (>$500K) | 10% |
| Repeat engagement | 10% |
| Pro bono | 100% (requires partner approval) |

## Expense Policy

- Travel billed at cost
- Materials at cost + 10%
- No markup on third-party fees

## Approval Requirements

- <$100K: Manager approval
- $100K-$500K: Partner approval
- >$500K: Practice head approval
"""
    },
]


def generate_sample_documents(output_dir: Path, count: int = None) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated = []
    documents = SAMPLE_DOCUMENTS[:count] if count else SAMPLE_DOCUMENTS
    
    for doc in documents:
        file_path = output_dir / doc["filename"]
        file_path.write_text(doc["content"])
        generated.append(str(file_path))
        print(f"Created: {file_path}")
    
    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate sample documents for testing"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=settings.data_raw_path,
        help="Output directory for sample documents",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Number of documents to generate (default: all)",
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    print(f"\nGenerating sample documents in: {output_dir}")
    print("-" * 50)
    
    generated = generate_sample_documents(output_dir, args.count)
    
    print("-" * 50)
    print(f"Generated {len(generated)} sample documents")
    print(f"\nNext steps:")
    print(f"1. Run: python scripts/init_db.py")
    print(f"2. Run: python scripts/ingest_documents.py --source {output_dir}")
    print(f"3. Start server: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
