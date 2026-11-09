"""Build readable search, comparison, and ranking-explanation reports."""

from agents.conversation import find_named_candidates, requested_count
from agents.screening import analyze_candidates


def build_search_report(rankings, resume_count=0):
    """Show first-round candidate evidence without a hiring decision."""
    report = [
        "# INITIAL SCREEN — TOP MATCHES",
        f"First round considered {resume_count} resume(s) and shortlisted "
        f"{len(rankings)} candidate(s).",
    ]
    detailed_candidates = analyze_candidates(rankings)

    if not detailed_candidates:
        return "# NO MATCHES FOUND\n\nTry broader skills or a lower experience threshold."

    for number, candidate in enumerate(detailed_candidates, start=1):
        report.extend([
            f"\n## {number}. {candidate['name']} — {candidate['score']}/100",
            f"- Strengths: {'; '.join(candidate['strengths'])}.",
            f"- Gaps: {'; '.join(candidate['gaps'])}.",
            f"- Suggestions: {'; '.join(candidate['suggestions'])}.",
            f"- Reasoning: {candidate['reasoning']}",
        ])

    report.append(
        "\nTo continue, ask to compare candidates, adjust criteria, "
        "request deep analysis, or ask for final-round decisions."
    )
    return "\n".join(report)


def build_comparison_report(message, rankings):
    """Compare named candidates or the requested number of top matches."""
    named_candidates = find_named_candidates(message, rankings)
    if len(named_candidates) >= 2:
        candidates = named_candidates[:10]
    else:
        count = requested_count(message, default=3)
        candidates = rankings[:max(2, count)]

    if len(candidates) < 2:
        return "There are not enough candidates in the current shortlist to compare."

    lines = [
        "| Candidate | Score | Skills found | Experience |",
        "|---|---:|---|---:|",
    ]
    for candidate in candidates:
        lines.append(
            f"| {candidate['name']} | {candidate['score']}/100 | "
            f"{', '.join(candidate['skills']) or 'Not detected'} | "
            f"{candidate.get('experience_years', 0)} years |"
        )
    return "# SIDE-BY-SIDE COMPARISON\n\n" + "\n".join(lines)


def build_ranking_explanation(message, rankings):
    """Explain a ranking using candidate scores and requirement evidence."""
    named_candidates = find_named_candidates(message, rankings)
    candidates = named_candidates[:2] if len(named_candidates) >= 2 else rankings[:2]

    if len(candidates) < 2:
        return "At least two ranked candidates are needed to explain a ranking difference."

    higher, lower = candidates
    details = [
        f"{higher['name']} scored {higher['score']}/100; "
        f"{lower['name']} scored {lower['score']}/100.",
        f"Experience evidence: {higher['name']} has "
        f"{higher.get('experience_years', 0)} years; "
        f"{lower['name']} has {lower.get('experience_years', 0)} years.",
        f"{higher['name']} matched skills: "
        f"{', '.join(higher['skills']) or 'none detected'}.",
        f"{lower['name']} matched skills: "
        f"{', '.join(lower['skills']) or 'none detected'}.",
        f"Score reasoning for {higher['name']}: {higher['reasoning']}",
        "Rankings are based only on extracted resume evidence and the active criteria.",
    ]

    if higher.get("missing_skills") != lower.get("missing_skills"):
        details.append(
            f"Missing required skills — {higher['name']}: "
            f"{', '.join(higher.get('missing_skills', [])) or 'none'}; "
            f"{lower['name']}: "
            f"{', '.join(lower.get('missing_skills', [])) or 'none'}."
        )

    return "\n".join(details)


def explain_ranking_changes(old_rankings, new_rankings):
    """Summarize how refinement changed candidate positions and scores."""
    old_positions = {
        candidate["name"]: (position, candidate["score"])
        for position, candidate in enumerate(old_rankings, start=1)
    }
    lines = ["# RANKING CHANGES AFTER REFINEMENT"]

    for new_position, candidate in enumerate(new_rankings, start=1):
        previous = old_positions.get(candidate["name"])
        if previous is None:
            change = "New in the shortlist"
        else:
            old_position, old_score = previous
            movement = old_position - new_position
            if movement > 0:
                direction = f"up {movement} place(s)"
            elif movement < 0:
                direction = f"down {abs(movement)} place(s)"
            else:
                direction = "same position"
            change = (
                f"{direction}; score changed from {old_score} "
                f"to {candidate['score']}"
            )

        lines.append(
            f"- {new_position}. {candidate['name']}: {change}. "
            f"Matched skills: {', '.join(candidate['skills']) or 'none detected'}."
        )

    return "\n".join(lines)
