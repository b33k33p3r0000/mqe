## Forensics Context

{{FORENSICS_JSON}}

## Adversarial Analysis Instructions

Based on the forensics context above, generate 3-5 adversarial hypotheses specific to THIS run and the changes made. For each hypothesis:

1. State the hypothesis
2. What evidence supports it (reference specific numbers)
3. What evidence contradicts it
4. Verdict: CONFIRMED / REFUTED / INCONCLUSIVE

**Focus areas based on the diff:**
- If search space was narrowed: "Is improvement from eliminating bad trials?"
- If score improved significantly: "Is the improvement real or statistical noise?"
- If DD decreased: "Did optimizer game the DD floor?"
- If pair count changed: "Is improvement from pair elimination?"

Output your findings as a JSON block in your decision.json under a "forensics" key:

```json
{
    "forensics": {
        "findings": [
            {
                "hypothesis": "...",
                "evidence_for": "...",
                "evidence_against": "...",
                "verdict": "CONFIRMED|REFUTED|INCONCLUSIVE",
                "severity": "CRITICAL|WARNING|INFO"
            }
        ],
        "critical_blocks": [],
        "warnings": [],
        "confidence": "HIGH|MEDIUM|LOW"
    }
}
```

**Rules:**
- CRITICAL findings MUST go into critical_blocks.
- WARNING findings go into warnings.
- Be specific: reference actual numbers.
- If quick checks already flagged issues, incorporate those findings.
