#!/bin/bash
# protect-files.sh — block edits to sensitive files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Exact basename matches (e.g. .env but not .env.example)
EXACT_NAMES=(".env" "uv.lock" "base_resume.json")

# Prefix/substring matches (e.g. anything inside .git/)
PREFIX_PATTERNS=(".git/")

BASENAME=$(basename "$FILE_PATH")

for name in "${EXACT_NAMES[@]}"; do
  if [[ "$BASENAME" == "$name" ]]; then
    echo "Blocked: '$FILE_PATH' is a protected file. Do not modify this file directly." >&2
    exit 2
  fi
done

for pattern in "${PREFIX_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: '$FILE_PATH' matches protected pattern '$pattern'. Do not modify this file directly." >&2
    exit 2
  fi
done

exit 0
