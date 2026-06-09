---
name: pr-description
description: Writes pull request descriptions. Use when creating a PR, writing a PR, or when the user asks to summarize changes for a pull request.
allowed-tools:
  - Bash
---

When writing a PR description:

1. Run `git diff main...HEAD` to see all changes on this branch
2. Write a description following this format:

## What
One sentence explaining what this PR does.

## Why
Brief context on why this change is needed.

## Changes
- Bullet points of specific changes made
- Group related changes together
- Mention any files deleted or renamed

## Testing
How to verify this works. Include specific commands if relevant.

- Run unit tests: `uv run pytest`
- If UI related: include a screenshot
- If API endpoint related: include a Postman test example

Keep descriptions concise. Focus on what a reviewer needs to know.
