# AGENTS.md

This repository contains a portable Moodle homework workflow.

If the user sends this repository URL and no local configuration exists, start the chat-led onboarding flow described in `skills/homework-runner/references/onboarding.md`. Do not ask the user to run a `setup` command.

For any request to complete, rebuild, resubmit, or verify a chapter assignment:

1. Read `skills/homework-runner/SKILL.md` completely.
2. Follow its workflow and read `skills/homework-runner/references/data-contract.md` before writing answer files.
3. Use your own image-reading capability for local textbook images. In Codex, use `view_image`.
4. Run the project CLI through `python scripts/homework.py`.
5. Never print credentials or commit runtime configuration.
6. Treat submission as a separate destructive action. Only submit when the user's request explicitly includes submission or resubmission.
