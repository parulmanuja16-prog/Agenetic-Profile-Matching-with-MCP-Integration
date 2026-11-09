"""Small helpers that identify the intent of a user's chat message."""

import re


def identify_intent(message, has_previous_search):
    """Choose whether a message searches, compares, explains, or refines."""
    text = message.casefold()

    if re.search(r"\b(screening|interview)\s+questions?\b", text):
        return "screening_questions"
    if "deep analysis" in text or "second round" in text:
        return "deep_analysis"
    if re.search(
        r"\b(final hire|hire/no-hire|hire or no hire|final recommendation|"
        r"final decision|final hiring)\b",
        text,
    ):
        return "final_decision"
    if re.search(r"\b(compare|side.by.side|comparison)\b", text):
        return "compare"
    if re.search(r"\b(why|explain)\b", text):
        return "explain"

    refinement_words = (
        "prioritize", "prefer", "add", "remove", "drop", "ignore",
        "require", "instead", "raise", "lower", "change", "at least",
    )
    if has_previous_search and any(word in text for word in refinement_words):
        return "refine"

    return "search"


def requested_count(message, default=3):
    """Read a requested count in numeric or word form."""
    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    count_pattern = r"(\d+|" + "|".join(number_words) + r")"
    match = re.search(
        rf"\b(?:top|first|compare(?:\s+the)?(?:\s+top)?)\s+{count_pattern}\b",
        message.casefold(),
    )
    if not match:
        return default

    value = match.group(1)
    return int(value) if value.isdigit() else number_words[value]


def find_named_candidates(message, rankings):
    """Return shortlisted candidates whose names appear in the message."""
    text = message.casefold()
    mentioned = []

    for candidate in rankings:
        name = candidate["name"]
        name_parts = name.casefold().split()
        full_name_position = text.find(name.casefold())

        if full_name_position >= 0:
            mentioned.append((full_name_position, candidate))
            continue

        # First-name matching supports questions such as "John vs Jane".
        for name_part in name_parts:
            match = re.search(rf"(?<!\w){re.escape(name_part)}(?!\w)", text)
            if match:
                mentioned.append((match.start(), candidate))
                break

    mentioned.sort(key=lambda item: item[0])
    return [candidate for _, candidate in mentioned]
