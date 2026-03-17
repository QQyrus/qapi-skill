# QAPI Test Creation Skill

This repository contains a reusable AI skill that scans a codebase for HTTP API endpoints, builds
QAPI-format test payloads, and saves them to a QAPI workspace through the bundled Python client.

## Repository Contents

```text
qapi-skill/
├── SKILL.md                # Core agent instructions
├── agents/openai.yaml      # Optional UI metadata for skill-capable clients
├── scripts/qapi_client.py  # QAPI REST client used by the skill
└── README.md               # Installation and usage notes
```

## Prerequisites

- Python 3.8+
- `requests` installed: `pip install requests`
- A QAPI account with:
  - `QAPI_API_TOKEN`
  - `QAPI_GATEWAY_TOKEN`
  - `QAPI_USER_EMAIL`

## Environment Variables

Set these before invoking the skill:

```bash
export QAPI_API_TOKEN="your-personal-api-token"
export QAPI_GATEWAY_TOKEN="your-gateway-token"
export QAPI_USER_EMAIL="you@example.com"
export QAPI_APP_URL="qapi.qyrus.com"
```

The bundled client also sends `scope: AI_SDK` on every QAPI API request automatically.

Supported `QAPI_APP_URL` values:

- `qapi.qyrus.com`
- `stg-api.qyrus.com`

Any other hostname is rejected on purpose so the client does not accidentally write to the wrong
environment.

## Quick Start

1. Clone this repository somewhere stable.
2. Export the `QAPI_*` environment variables.
3. Install or reference the skill in your assistant of choice.
4. Invoke the skill and point it at the codebase you want scanned.

## Installation

### One-Command Install with `npx skills`

`npx skills` is the simplest install path.

Interactive install:

```bash
npx skills add QQyrus/qapi-skill
```

Full GitHub URL also works:

```bash
npx skills add https://github.com/QQyrus/qapi-skill
```

Useful non-interactive examples:

```bash
# Install globally for Claude Code
npx skills add QQyrus/qapi-skill -g -a claude-code -y

# Install globally for Codex
npx skills add QQyrus/qapi-skill -g -a codex -y

# Install globally for Cursor
npx skills add QQyrus/qapi-skill -g -a cursor -y

# Install globally for Antigravity
npx skills add QQyrus/qapi-skill -g -a antigravity -y
```

Why this works for this repository:

- The `skills` CLI supports GitHub shorthand and full GitHub URLs.
- It can prompt for the target agent if none is specified.
- It discovers skills in the repository root when the root contains `SKILL.md`, which this repo does.

### Claude Code

Claude Code supports skill folders directly. If you do not want to use `npx skills`, manual install
still works:

Global install:

```bash
mkdir -p ~/.claude/skills
ln -s /absolute/path/to/qapi-skill ~/.claude/skills/qapi-create-tests
```

Project-local install:

```bash
mkdir -p .claude/skills
ln -s /absolute/path/to/qapi-skill .claude/skills/qapi-create-tests
```

Usage:

```text
/qapi-create-tests
```

### Codex

Codex uses skill folders under `$CODEX_HOME/skills` and can also discover skills referenced from
`AGENTS.md`. If you do not want to use `npx skills`, manual install still works:

Personal install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s /absolute/path/to/qapi-skill "${CODEX_HOME:-$HOME/.codex}/skills/qapi-create-tests"
```

Repo-local usage through `AGENTS.md`:

```md
[$qapi-create-tests](/absolute/path/to/qapi-skill/SKILL.md)
```

When using the skill explicitly, reference it by name or by the absolute `SKILL.md` path.

### Cursor

Cursor does not use Codex-style skill folders. Use a project rule that tells Cursor to follow this
skill, and keep this repository in the workspace so `scripts/qapi_client.py` remains executable.
`npx skills` can also install directly to Cursor.

Create `.cursor/rules/qapi-create-tests.mdc`:

```md
---
description: Generate and save QAPI API tests with the local qapi-create-tests skill
globs:
alwaysApply: false
---

Read `/absolute/path/to/qapi-skill/SKILL.md` and follow its execution workflow when asked to create
or save QAPI tests.
```

Then trigger it from Cursor Chat by naming the rule or asking Cursor to use the QAPI test creation
workflow.

### Antigravity

If your Antigravity setup supports reusable workspace rules or prompts, add one that points at this
skill and keep this repository checked out locally. `npx skills` can also install directly to
Antigravity.

```text
Read /absolute/path/to/qapi-skill/SKILL.md and follow it for QAPI test generation and save flows.
Use the local scripts/qapi_client.py helper for all QAPI API calls.
```

The important requirement is that Antigravity can read `SKILL.md` and execute the bundled Python
script from the same checkout.

### Windsurf

Add a workspace rule such as `.windsurf/rules/qapi-create-tests.md` with a short instruction to read
`/absolute/path/to/qapi-skill/SKILL.md`, then ask Windsurf to use that workflow.

### GitHub Copilot / Other Prompt-Driven Assistants

These clients generally do not have a native skill install path. Reuse the skill by pasting a short
instruction that points at `SKILL.md`, for example:

```text
Use the qapi-create-tests skill at /absolute/path/to/qapi-skill/SKILL.md and execute it against this repository.
```

