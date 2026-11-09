"""Start an interactive resume-matching conversation in the terminal."""

from agents.matching_agent import run_agent


def main():
    """Read natural-language requests and keep the latest shortlist in memory."""
    print("Agentic Profile Matching")
    print("Type a job search or follow-up request. Type 'exit' to quit.")
    print("Examples: compare top 3, why did John rank higher than Jane,")
    print("prioritize Python, deep analysis, final hire recommendation.")

    conversation_state = None

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if message.casefold() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not message:
            continue

        conversation_state = run_agent(message, conversation_state)
        print("\nAgent:")
        print(conversation_state["final_report"])


if __name__ == "__main__":
    main()
