"""10 realistic staff "what-if" questions for testing Kiro's grounding.

Run this script to send each question through the Bedrock integration and
print responses. Manually verify:
  1. Kiro cites actual numbers from the precomputed JSON
  2. Kiro refuses gracefully when data is missing
  3. Kiro never invents data not in the JSON

Usage:
    python -m bedrock.test_questions
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.handlers._data import load_mined_data
from bedrock.client import answer_question

QUESTIONS = [
    # Should answer (data exists)
    "What if we can only run one section of ACCT 2200?",
    "Which courses are taken together most frequently by BA freshmen?",
    "Can we drop MATH 1030 from the freshman block without affecting most students?",
    "What's the runner-up schedule if we remove ECON 2010?",
    "How many students historically took ENGL 1109 and MATH 1010 in the same term?",
    "If we add a section of BCOM 2010, does it fit the 14-15 unit range?",
    "Are there courses that almost never appear together in the same term?",
    # Should refuse gracefully (out of scope or missing data)
    "What would a 12-unit schedule look like for BA freshmen?",
    "What about Psychology majors — what's their top schedule?",
    "What's the demand for evening sections of COMM 1008?",
]


def main():
    data = load_mined_data()
    print(f"Loaded mined data: {len(data['terms'])} terms\n")
    print("=" * 70)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'='*70}")
        print(f"Q{i}: {question}")
        print("-" * 70)
        try:
            answer = answer_question(question, data)
            print(f"A: {answer}")
        except Exception as e:
            print(f"ERROR: {e}")
        print()


if __name__ == "__main__":
    main()
