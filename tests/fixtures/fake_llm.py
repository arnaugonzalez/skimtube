"""Deterministic stand-in for an LLM CLI: reads the prompt on stdin, prints Markdown."""
import sys

prompt = sys.stdin.read()
if "FAIL" in prompt:
    sys.stderr.write("simulated provider outage\n")
    sys.exit(1)
if "write a DIGEST" in prompt or "Write a DIGEST" in prompt:
    contradiction = "CLAIM-OPEN" in prompt and "CLAIM-CLOSED" in prompt
    print("## Themes\n### Open models\n- A new open model was released [1][2]\n")
    print("## Contradictions (A vs B)")
    if contradiction:
        print("- **Licence of the model**\n  - **A** ([1]): open weights\n"
              "  - **B** ([2]): closed weights\n  - *Note*: different dates")
    else:
        print("No contradictions detected in this window.")
    print("\n## Weak signals\n- none\n\n## Sources\n1. [1]\n2. [2]")
elif "sourdough" in prompt:
    print("SKIP: not relevant")
else:
    print("## TL;DR\n- A new open model scores 71% on reasoning\n\n## Key topics\n- LLMs\n\n"
          "## What's new\n- **New models**: ExampleLM\n\n## Entities\n- ExampleLM\n\n"
          "## Facts and figures\n- 71%")
