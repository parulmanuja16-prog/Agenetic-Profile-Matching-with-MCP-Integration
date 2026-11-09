"""Generate second-round evidence analysis and final hiring decisions."""


def analyze_candidates(candidates):
    """Add evidence-based strengths, gaps, and follow-up suggestions."""
    analyzed = []

    for candidate in candidates:
        result = dict(candidate)
        strengths = []
        gaps = []
        suggestions = list(result.get("suggestions", []))

        if result.get("skills"):
            strengths.append(
                f"Resume evidence matches: {', '.join(result['skills'])}"
            )
        if result.get("experience_years", 0):
            strengths.append(
                f"{result['experience_years']} years of experience were identified"
            )

        if result.get("missing_skills"):
            gaps.append(
                f"Required skills not found: {', '.join(result['missing_skills'])}"
            )
        required_years = result.get("required_experience", 0)
        candidate_years = result.get("experience_years", 0)
        if required_years and candidate_years < required_years:
            gaps.append(
                f"Experience evidence is {candidate_years} years; "
                f"the requirement is {required_years}+"
            )

        if 55 <= result.get("score", 0) < 70 and not suggestions:
            suggestions.append(
                "Use a focused technical interview to verify the candidate's "
                "hands-on experience."
            )
        if not suggestions:
            suggestions.append(
                "Verify project ownership and impact during the interview."
            )

        result["strengths"] = strengths or ["Relevant resume evidence was found"]
        result["gaps"] = gaps or ["No explicit requirement gaps were detected"]
        result["suggestions"] = suggestions
        analyzed.append(result)

    return analyzed


def make_final_decision(candidate):
    """Apply required-criteria gates and the project's score thresholds."""
    if candidate.get("missing_skills"):
        return "NO-HIRE"

    required_years = candidate.get("required_experience", 0)
    if required_years and candidate.get("experience_years", 0) < required_years:
        return "NO-HIRE"

    if candidate["score"] >= 70:
        return "HIRE"
    return "NO-HIRE"


def build_deep_analysis(candidates):
    """Format detailed second-round evidence for each shortlisted candidate."""
    report = ["# SECOND-ROUND DEEP ANALYSIS"]

    for number, candidate in enumerate(analyze_candidates(candidates), start=1):
        report.extend([
            f"\n## {number}. {candidate['name']}",
            f"- Match score: {candidate['score']}/100",
            f"- Strengths: {'; '.join(candidate['strengths'])}.",
            f"- Gaps: {'; '.join(candidate['gaps'])}.",
            f"- Follow-up suggestions: {'; '.join(candidate['suggestions'])}.",
            f"- Evidence: {candidate['reasoning']}",
        ])

    return "\n".join(report)


def build_screening_questions(job_description, requirements):
    """Create role-focused questions from the active job criteria."""
    skill_names = {
        "aws": "AWS",
        "c++": "C++",
        "c#": "C#",
        "gcp": "GCP",
        "javascript": "JavaScript",
        "node.js": "Node.js",
        "sql": "SQL",
        "typescript": "TypeScript",
    }

    def display_skill(skill):
        return skill_names.get(skill.casefold(), skill.title())

    required_skills = requirements.get("must_have_skills", [])
    preferred_skills = requirements.get("preferred_skills", [])
    experience = requirements.get("experience", 0)
    questions = []

    for skill in required_skills:
        questions.append(
            f"Describe a project where you used {display_skill(skill)} "
            "to solve a problem "
            "relevant to this role. What was your contribution?"
        )
    for skill in preferred_skills:
        questions.append(
            f"What hands-on experience do you have with {display_skill(skill)}, "
            "and how could you apply it in this role?"
        )
    if experience:
        questions.append(
            f"The role asks for at least {experience} years of experience. "
            "Which projects best demonstrate the depth and impact of your work?"
        )

    questions.extend([
        "Walk me through a recent project most relevant to this job description. "
        "What were your responsibilities and results?",
        "Based on this job description, what would you prioritize in your first "
        "90 days, and how would you measure progress?",
        "Describe a challenging technical problem you solved. What options did "
        "you consider, and why did you choose your approach?",
        "How do you test your work and make sure it remains reliable after release?",
    ])
    questions = questions[:8]

    context = []
    if job_description.strip():
        context.append("Based on the active job description")
    if required_skills:
        context.append(
            f"Required skills: {', '.join(display_skill(skill) for skill in required_skills)}"
        )
    if preferred_skills:
        context.append(
            f"Preferred skills: {', '.join(display_skill(skill) for skill in preferred_skills)}"
        )
    if experience:
        context.append(f"Minimum experience: {experience} years")
    if not context:
        context.append("Questions are based on the active job description")

    report = [
        "# SCREENING QUESTIONS",
        f"_{'; '.join(context)}._",
    ]
    report.extend(
        f"{number}. {question}"
        for number, question in enumerate(questions, start=1)
    )
    return "\n\n".join(report)


def build_final_decisions(candidates):
    """Format one final hire/no-hire decision for every analyzed candidate."""
    report = ["# FINAL HIRING RECOMMENDATIONS"]

    for candidate in analyze_candidates(candidates):
        report.extend([
            f"\n## {candidate['name']}",
            f"- Decision: {make_final_decision(candidate)}",
            f"- Match score: {candidate['score']}/100",
            f"- Strengths: {'; '.join(candidate['strengths'])}.",
            f"- Gaps: {'; '.join(candidate['gaps'])}.",
            f"- Suggested follow-up: {'; '.join(candidate['suggestions'])}.",
        ])

    return "\n".join(report)
