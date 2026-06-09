import pathlib

api_path = pathlib.Path("c:/Users/Parth/Desktop/Github/baised/backend/api.py")
content = api_path.read_text("utf-8")

# 1. Update _build_fallback_ai_report
fallback_old = """    confidence = "LOW" if row_count < 30 else "MEDIUM" if row_count < 100 else "HIGH"
    return {
        "severity_label": severity_label,
        "severity_color": severity_color,
        "headline": f"{least_advantaged} faces materially lower favorable outcomes than {most_advantaged}.",
        "metrics_summary": f"**DIR**={dir_value}, **SPD**={spd_value}, **Bias Score**={bias_score}. Current run indicates {severity_label} disparity risk.",
        "root_cause": {
            "primary_driver": top_feature,
            "explanation": f"The largest disparity signal aligns with {top_feature}. Feature distribution and threshold effects likely amplify outcome gaps for {least_advantaged}.",
        },
        "group_comparison": {
            "most_advantaged": most_advantaged,
            "least_advantaged": least_advantaged,
            "disparity_ratio": disparity_ratio,
            "plain_english": f"A person in {least_advantaged} is currently less likely to receive the same favorable outcome as someone in {most_advantaged}.",
        },
        "recommended_actions": recommended_actions,
        "compliance_flags": [
            "Potential discrimination risk requires documented mitigation and periodic bias monitoring under applicable fairness governance obligations."
        ],
        "confidence": confidence,
        "confidence_reason": f"Confidence is {confidence} based on sample size ({row_count} rows) and deterministic metric consistency.",
    }"""

fallback_new = """    confidence = "LOW" if row_count < 30 else "MEDIUM" if row_count < 100 else "HIGH"
    return {
        "severity_label": severity_label,
        "severity_color": severity_color,
        "headline": f"{least_advantaged} faces materially lower favorable outcomes than {most_advantaged}.",
        "metrics_summary": f"**DIR**={dir_value}, **SPD**={spd_value}, **Bias Score**={bias_score}. Current run indicates {severity_label} disparity risk.",
        "root_cause": {
            "primary_driver": top_feature,
            "explanation": f"The largest disparity signal aligns with {top_feature}. Feature distribution and threshold effects likely amplify outcome gaps for {least_advantaged}.",
        },
        "group_comparison": {
            "most_advantaged": most_advantaged,
            "least_advantaged": least_advantaged,
            "disparity_ratio": disparity_ratio,
            "plain_english": f"A person in {least_advantaged} is currently less likely to receive the same favorable outcome as someone in {most_advantaged}.",
        },
        "recommended_actions": recommended_actions,
        "compliance_flags": [
            "Potential discrimination risk requires documented mitigation and periodic bias monitoring under applicable fairness governance obligations."
        ],
        "confidence": confidence,
        "confidence_reason": f"Confidence is {confidence} based on sample size ({row_count} rows) and deterministic metric consistency.",
        "executive_summary": f"Audit of {row_count} records shows {severity_label} bias toward {least_advantaged}.",
        "technical_audit": f"DIR is {dir_value} and SPD is {spd_value}. Top proxy feature: {top_feature}.",
        "pattern_detected": analysis_data.get("bias_pattern", {}).get("pattern_type", "None"),
        "proxy_risks": [],
        "compliance_risks": ["Periodic bias monitoring recommended."],
        "mitigation_plan": recommended_actions,
        "confidence_notes": f"Based on {row_count} rows.",
    }"""

content = content.replace(fallback_old, fallback_new)

# 2. Update _normalize_ai_report
norm_old = """    severity_label, severity_color = _severity_tokens(str(merged.get("severity_label", fallback["severity_label"])))
    merged["severity_label"] = severity_label
    merged["severity_color"] = severity_color
    merged["headline"] = str(merged.get("headline", fallback["headline"]))[:160]
    merged["metrics_summary"] = str(merged.get("metrics_summary", fallback["metrics_summary"]))
    merged["confidence"] = str(merged.get("confidence", fallback["confidence"])).upper()
    merged["confidence_reason"] = str(merged.get("confidence_reason", fallback["confidence_reason"]))
    return merged"""

norm_new = """    severity_label, severity_color = _severity_tokens(str(merged.get("severity_label", fallback["severity_label"])))
    merged["severity_label"] = severity_label
    merged["severity_color"] = severity_color
    merged["headline"] = str(merged.get("headline", fallback["headline"]))[:160]
    merged["metrics_summary"] = str(merged.get("metrics_summary", fallback["metrics_summary"]))
    merged["confidence"] = str(merged.get("confidence", fallback["confidence"])).upper()
    merged["confidence_reason"] = str(merged.get("confidence_reason", fallback["confidence_reason"]))
    
    # Normalize new fields
    merged["executive_summary"] = str(merged.get("executive_summary", fallback["executive_summary"]))
    merged["technical_audit"] = str(merged.get("technical_audit", fallback["technical_audit"]))
    merged["pattern_detected"] = str(merged.get("pattern_detected", fallback["pattern_detected"]))
    
    proxy_risks = merged.get("proxy_risks")
    if not isinstance(proxy_risks, list):
        merged["proxy_risks"] = fallback["proxy_risks"]
        
    comp_risks = merged.get("compliance_risks")
    if not isinstance(comp_risks, list):
        merged["compliance_risks"] = fallback["compliance_risks"]
        
    mit_plan = merged.get("mitigation_plan")
    if not isinstance(mit_plan, list):
        merged["mitigation_plan"] = fallback["mitigation_plan"]
        
    merged["confidence_notes"] = str(merged.get("confidence_notes", fallback["confidence_notes"]))
    return merged"""

content = content.replace(norm_old, norm_new)


# 3. Update ai_analyze schema
schema_old = """        "Return ONLY this exact JSON schema (no extra fields, no markdown):\\n"
        "{\\n"
        '  "severity_label": "HIGH | MEDIUM | LOW",\\n'
        '  "severity_color": "red | amber | green",\\n'
        '  "headline": "One punchy sentence (max 20 words) describing the core bias finding",\\n'
        '  "metrics_summary": "2 sentences max. Mention DIR, SPD, Bias Score. Bold key terms with **.",\\n'
        '  "root_cause": {\\n'
        '    "primary_driver": "Human-readable feature name (NOT raw column name)",\\n'
        '    "explanation": "2-3 sentences explaining WHY this feature causes disparity."\\n'
        "  },\\n"
        '  "group_comparison": {\\n'
        '    "most_advantaged": "group name",\\n'
        '    "least_advantaged": "group name",\\n'
        '    "disparity_ratio": "e.g. 2.3x",\\n'
        '    "plain_english": "1 sentence impact statement for least advantaged group"\\n'
        "  },\\n"
        '  "recommended_actions": [\\n'
        '    {"priority": "IMMEDIATE", "action": "Specific action sentence"},\\n'
        '    {"priority": "SHORT_TERM", "action": "Specific action sentence"},\\n'
        '    {"priority": "LONG_TERM", "action": "Specific action sentence"}\\n'
        "  ],\\n"
        '  "compliance_flags": ["One-line compliance concern"],\\n'
        '  "confidence": "HIGH | MEDIUM | LOW",\\n'
        '  "confidence_reason": "One sentence confidence rationale"\\n'
        "}\""""

schema_new = """        "Return ONLY this exact JSON schema (no extra fields, no markdown):\\n"
        "{\\n"
        '  "severity_label": "HIGH | MEDIUM | LOW",\\n'
        '  "severity_color": "red | amber | green",\\n'
        '  "headline": "One punchy sentence (max 20 words) describing the core bias finding",\\n'
        '  "metrics_summary": "2 sentences max. Mention DIR, SPD, Bias Score. Bold key terms with **.",\\n'
        '  "root_cause": {\\n'
        '    "primary_driver": "Human-readable feature name (NOT raw column name)",\\n'
        '    "explanation": "2-3 sentences explaining WHY this feature causes disparity."\\n'
        "  },\\n"
        '  "group_comparison": {\\n'
        '    "most_advantaged": "group name",\\n'
        '    "least_advantaged": "group name",\\n'
        '    "disparity_ratio": "e.g. 2.3x",\\n'
        '    "plain_english": "1 sentence impact statement for least advantaged group"\\n'
        "  },\\n"
        '  "recommended_actions": [\\n'
        '    {"priority": "IMMEDIATE", "action": "Specific action sentence"},\\n'
        '    {"priority": "SHORT_TERM", "action": "Specific action sentence"},\\n'
        '    {"priority": "LONG_TERM", "action": "Specific action sentence"}\\n'
        "  ],\\n"
        '  "compliance_flags": ["One-line compliance concern"],\\n'
        '  "confidence": "HIGH | MEDIUM | LOW",\\n'
        '  "confidence_reason": "One sentence confidence rationale",\\n'
        '  "executive_summary": "1 paragraph overview of the audit.",\\n'
        '  "technical_audit": "Detailed technical breakdown of metrics.",\\n'
        '  "pattern_detected": "PROXY_BIAS | INTERSECTIONAL_HIDDEN_BIAS | SMALL_SAMPLE_UNRELIABLE | None",\\n'
        '  "proxy_risks": [{"feature": "...", "risk": "HIGH", "explanation": "..."}],\\n'
        '  "compliance_risks": ["Specific risk point"],\\n'
        '  "mitigation_plan": [\\n'
        '    {"priority": "IMMEDIATE", "action": "Detailed step"}\\n'
        "  ],\\n"
        '  "confidence_notes": "Additional sample size caveats"\\n'
        "}\""""

content = content.replace(schema_old, schema_new)

api_path.write_text(content, "utf-8")
print("Done writing api.py")
