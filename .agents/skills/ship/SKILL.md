---
name: ship
description: Stages changes, commits with a concise message (or user-provided comment), pushes the current branch to origin, and opens a well-documented Pull Request. Trigger with /ship.
---

# Ship Workflow (/ship)

When the user triggers `/ship` (e.g. `/ship` or `/ship "custom commit message"`):

## Execution Steps

1. **Inspect Working Directory & Branch:**
   - Inspect active branch and status (`git status`).
   - If on `main`, inform the user and confirm whether to create a feature branch first.

2. **Determine Commit Message:**
   - If the user specified a custom message or comment in their command (e.g., `/ship "fix: resolve auth crash"`), use their exact comment.
   - If left blank, inspect `git status` and `git diff` to craft a professional Conventional Commit message (e.g., `feat(...)`, `fix(...)`, `refactor(...)`).

3. **Stage & Commit:**
   - Stage changes (`git add .`).
   - Commit with the determined message (`git commit -m "<message>"`).

4. **Push Branch:**
   - Push the branch to remote origin (`git push origin <branch_name>`).

5. **Create Pull Request:**
   - Create a Pull Request against `main` using GitHub MCP tool or git/gh CLI.
   - Include a comprehensive PR description detailing summary of changes, components touched, and test verification status.
   - Share the PR URL with the user.
