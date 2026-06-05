#!/bin/bash
# protect-files.sh — block access to sensitive files

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Block path traversal attacks
if [[ "$FILE_PATH" == *".."* ]]; then
  echo "Blocked: path traversal detected in '$FILE_PATH'." >&2
  exit 2
fi

# Fully protected — no read or write allowed
PROTECTED=(".env")

# Write-only protected — Claude may read but not modify
WRITE_ONLY=("uv.lock" "base_resume.json")
WRITE_PATTERNS=(".git/")

BASENAME=$(basename "$FILE_PATH")

for name in "${PROTECTED[@]}"; do
  if [[ "$BASENAME" == "$name" ]]; then
    echo "Blocked: '$FILE_PATH' is protected — read and write are not allowed." >&2
    exit 2
  fi
done

if [[ "$TOOL" == "Edit" || "$TOOL" == "MultiEdit" || "$TOOL" == "Write" ]]; then
  for name in "${WRITE_ONLY[@]}"; do
    if [[ "$BASENAME" == "$name" ]]; then
      echo "Blocked: '$FILE_PATH' is write-protected. Do not modify this file directly." >&2
      exit 2
    fi
  done

  for pattern in "${WRITE_PATTERNS[@]}"; do
    if [[ "$FILE_PATH" == *"$pattern"* ]]; then
      echo "Blocked: '$FILE_PATH' matches write-protected pattern '$pattern'." >&2
      exit 2
    fi
  done
fi

exit 0
