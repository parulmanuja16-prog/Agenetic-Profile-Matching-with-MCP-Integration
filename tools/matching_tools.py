"""Extract job criteria, score resume evidence, and create interview prompts."""

import re


SKILL_LIST = (
    "python", "java", "javascript", "typescript", "react", "node.js", "node",
    "sql", "django", "flask", "fastapi", "aws", "docker", "kubernetes",
    "azure", "gcp", "go", "rust", "c++", "c#", "postgresql", "mongodb",
    "redis", "kafka", "pytorch", "tensorflow", "langchain", "langgraph",
    "machine learning", "deep learning", "spark", "terraform", "linux",
)


def _contains_skill(text, skill):
    """Match a technology as a complete term, not as part of another word."""
    pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _skills_in(text):
    """Return known technology names that appear in a piece of text."""
    return [skill for skill in SKILL_LIST if _contains_skill(text, skill)]


def _skill_context(text, skill):
    """Return the punctuation-delimited phrase that contains one skill."""
    for phrase in re.split(r"[,;\n.!?]", text):
        if _contains_skill(phrase, skill):
            return phrase.casefold()
    return text.casefold()


def _comparative_skill_preferences(text):
    """Find skills explicitly preferred over another named skill."""
    favored = set()
    deprioritized = set()
    pattern = (
        r"\bprefer\s+(.+?)\s+over\s+(.+?)"
        r"(?=\b(?:and|but|while|whereas|plus)\b|[.!?;\n]|$)"
    )
    for match in re.finditer(pattern, text, re.IGNORECASE):
        favored.update(_skills_in(match.group(1)))
        deprioritized.update(_skills_in(match.group(2)))
    return favored, deprioritized


def extract_requirements(job_description, previous=None, feedback=""):
    """Find required skills and experience, applying an optional refinement."""
    if previous is None:
        source_text = job_description
        skills_text = job_description
        requirements = {"must_have_skills": [], "preferred_skills": [], "experience": 0}
    else:
        source_text = job_description
        skills_text = feedback
        requirements = {
            "must_have_skills": list(previous.get("must_have_skills", [])),
            "preferred_skills": list(previous.get("preferred_skills", [])),
            "experience": previous.get("experience", 0),
        }

    comparatively_preferred, deprioritized = _comparative_skill_preferences(
        skills_text
    )
    optional_words = ("prefer", "priorit", "nice to have", "optional", "bonus")
    for skill in _skills_in(skills_text):
        nearby_text = _skill_context(skills_text, skill)

        if skill in deprioritized:
            requirements["must_have_skills"] = [
                item for item in requirements["must_have_skills"]
                if item.casefold() != skill.casefold()
            ]
            requirements["preferred_skills"] = [
                item for item in requirements["preferred_skills"]
                if item.casefold() != skill.casefold()
            ]
        elif (
            skill in comparatively_preferred
            or any(word in nearby_text for word in optional_words)
        ):
            requirements["must_have_skills"] = [
                item for item in requirements["must_have_skills"]
                if item.casefold() != skill.casefold()
            ]
            if skill not in requirements["preferred_skills"]:
                requirements["preferred_skills"].append(skill)
        elif skill not in requirements["must_have_skills"]:
            requirements["must_have_skills"].append(skill)

    if previous is not None:
        for skill in _skills_in(feedback):
            nearby_text = _skill_context(feedback, skill)
            if re.search(r"\b(remove|drop|ignore|no longer require)\b", nearby_text, re.I):
                requirements["must_have_skills"] = [
                    item for item in requirements["must_have_skills"]
                    if item.casefold() != skill.casefold()
                ]
                requirements["preferred_skills"] = [
                    item for item in requirements["preferred_skills"]
                    if item.casefold() != skill.casefold()
                ]

    experience_text = feedback if previous is not None else job_description
    years = re.findall(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)\b", experience_text, re.I)
    if years:
        requirements["experience"] = max(int(value) for value in years)

    requirements["source_text"] = source_text
    return requirements


def _resume_experience(document):
    """Read an explicit years-of-experience value from a resume."""
    values = re.findall(
        r"\b(\d+)\s*\+?\s*(?:years?|yrs?)\b",
        document.page_content,
        re.IGNORECASE,
    )
    metadata_value = document.metadata.get("experience_years", 0)
    return max([int(value) for value in values] + [int(metadata_value or 0)])


def rank_candidates(results, requirements, top_k=10):
    """Score, explain, deduplicate, and return the highest-ranked resumes."""
    ranked = []
    required_skills = requirements.get("must_have_skills", [])
    preferred_skills = requirements.get("preferred_skills", [])
    required_experience = requirements.get("experience", 0)

    for document, distance in results:
        resume_text = document.page_content
        matched_required = [
            skill for skill in required_skills
            if _contains_skill(resume_text, skill)
        ]
        missing_required = [
            skill for skill in required_skills if skill not in matched_required
        ]
        matched_preferred = [
            skill for skill in preferred_skills
            if _contains_skill(resume_text, skill)
        ]
        experience = _resume_experience(document)
        semantic_score = max(0, 100 - float(distance) * 18)
        required_ratio = (
            len(matched_required) / len(required_skills)
            if required_skills else 0.5
        )
        preferred_ratio = (
            len(matched_preferred) / len(preferred_skills)
            if preferred_skills else 0
        )

        # Required skills weigh most; optional skills improve the score slightly.
        score = semantic_score * 0.5 + required_ratio * 40 + preferred_ratio * 10
        if required_experience and experience >= required_experience:
            experience_ratio = min(experience / required_experience, 2.0)
            score += experience_ratio * 5
        score = round(min(score, 99.5), 2)

        experience_gap = bool(required_experience and experience < required_experience)
        skills = matched_required + [
            skill for skill in matched_preferred if skill not in matched_required
        ]
        gaps = list(missing_required)
        if experience_gap:
            gaps.append(f"{required_experience}+ years of experience")

        reason = (
            f"Score {score}/100: semantic relevance {semantic_score:.1f}/100; "
            f"required skills matched {len(matched_required)}/{len(required_skills)}; "
            f"preferred skills matched {len(matched_preferred)}/{len(preferred_skills)}; "
            f"experience identified {experience} years."
        )
        ranked.append({
            "name": document.metadata.get("name", "Unknown"),
            "score": score,
            "skills": skills,
            "missing_skills": missing_required,
            "experience_years": experience,
            "required_experience": required_experience,
            "source": document.metadata.get("source"),
            "suggestions": [
                f"Verify experience with {skill} during screening."
                for skill in missing_required
            ],
            "semantic_score": round(semantic_score, 2),
            "reasoning": reason,
            "gaps": gaps,
        })
        if experience_gap:
            ranked[-1]["suggestions"].append(
                "Verify whether adjacent experience satisfies the minimum requirement."
            )

    unique_candidates = []
    seen_sources = set()
    for candidate in ranked:
        source = candidate["source"] or candidate["name"]
        if source not in seen_sources:
            unique_candidates.append(candidate)
            seen_sources.add(source)

    unique_candidates.sort(
        key=lambda candidate: (
            -candidate["score"],
            -candidate["experience_years"],
            candidate["name"].casefold(),
        )
    )
    return unique_candidates[:max(0, top_k)]


def compare_candidates(candidates):
    """Return a readable comparison of candidate scores and evidence."""
    lines = ["# CANDIDATE COMPARISON"]
    for number, candidate in enumerate(candidates, start=1):
        lines.extend([
            f"\n## {number}. {candidate['name']}",
            f"- Score: {candidate['score']}/100",
            f"- Skills found: {', '.join(candidate['skills']) or 'none'}",
            f"- Experience: {candidate.get('experience_years', 0)} years",
            f"- Gaps: {', '.join(candidate.get('gaps', [])) or 'none detected'}",
            f"- Reasoning: {candidate['reasoning']}",
        ])
    return "\n".join(lines)


def generate_interview_questions(candidate):
    """Create short screening questions from a candidate's matched skills."""
    questions = [
        f"Explain a project where you used {skill} and describe your contribution."
        for skill in candidate.get("skills", [])[:3]
    ]
    questions.extend([
        "Describe a challenging project and the technical decisions you made.",
        "How do you test and monitor the systems you build?",
    ])
    return questions[:5]
