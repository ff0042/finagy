---
name: sandbox
description: Emulates Claude Code sandbox mode with isolated branch execution, autonomous reads/network access, and paid API cost guardrails.
---

# Sandbox Execution Mode (`/sandbox`)

When the user starts a prompt with `/sandbox`, follow these operational directives:

## 0. Visual Indicators & Status Banner
* **Header Banner**: Every response while operating in Sandbox Mode MUST begin with an explicit visual status banner:
  > 🧪 **[SANDBOX MODE ACTIVE]** — *Isolated Branch Workspace | Full In-Branch Autonomy | Paid API Guardrail ON*
* Clearly state the isolated branch name/workspace path so the user knows changes are sandboxed.

## 1. Branch Selection & Creation Rules (STRICT CONTROL)
* **Check Current Branch First**: Run `git branch --show-current` to identify the active branch.
* **Rule A (On Non-Main Branch, No Branch Specified)**: If currently on a non-main branch (e.g., `feature/xyz`) and no `<branch-name>` argument was given in `/sandbox`, proceed using the **current active branch** without creating a new branch.
* **Rule B (On `main` Branch, No Branch Specified)**: If currently on `main` and no `<branch-name>` argument was given:
  - STOP immediately.
  - List available local/remote git branches (`git branch -a`).
  - Ask the user to select an existing branch or specify a new branch name.
* **Rule C (Explicit Branch Specified: `/sandbox <branch-name>`)**:
  - Check if `<branch-name>` exists (`git branch --list <branch-name>`).
  - If it **exists**: Switch to / use that branch.
  - If it **does NOT exist**: **ASK PERMISSION FIRST** before creating the new branch (e.g., *"Branch '<branch-name>' does not exist. Would you like me to create it off current branch?"*). Never create a new branch without explicit approval.

## 2. Permission & Autonomy Rules
* **In-Branch Modifications**: Full autonomy. Proceed automatically with all file creations, edits, and terminal commands within the branch workspace.
* **Outside-Branch Modifications**: **STRICT GUARDRAIL**. If any operation attempts to modify files outside the isolated branch workspace, STOP and prompt the user for permission.
* **Read Operations**: Full autonomy. Always proceed immediately with reading files, searching code, listing directories, or viewing system state.
* **Network Requests**: Full autonomy. Always proceed with web searches, URL fetching, dependency downloads, and standard non-paid HTTP requests.
* **Paid API & Cost Guardrail**: **STRICT GUARDRAIL**. Do NOT autonomously execute scripts or tests that invoke paid external APIs (such as OpenRouter, paid LLMs, or paid cloud APIs) unless the user explicitly requested that specific test or paid call in their prompt. Ask the user for explicit approval first.

## 3. Reporting & Merge Protocol
* Once work in the sandbox branch is complete, summarize the changes, test results, and diffs to the user.
* Ask the user if they wish to merge the sandbox branch changes back into the main working tree.
