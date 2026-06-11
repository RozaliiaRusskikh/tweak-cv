# Slack Block Kit Contract

**File**: `tweakcv/nodes/notify.py` + `tweakcv/slack_handler.py`

## Review Message Structure

Posted by `notify_node` to `SLACK_CHANNEL_ID`. Updated (not re-posted) on each edit iteration.

### Blocks (in order)

| # | Block type | Content | Condition |
|---|-----------|---------|-----------|
| 1 | `header` | `"{company} – {role}"` | Always |
| 2 | `section` | Resume `summary` text | Always |
| 3 | `section` | Score display: `keyword_coverage`, `no_hallucination` | Always |
| 4 | `context` | `"⚠️ This is your last edit – approve or reject after this"` | Only when `iteration == 3` |
| 5 | `actions` | Approve / Edit / Reject buttons (see below) | Always |

### Action Buttons

| `action_id` | Label | Style | Value | Shown when |
|-------------|-------|-------|-------|------------|
| `approve_resume` | Approve | `"primary"` | `"{job_id}"` | Always |
| `edit_resume` | Edit | (default) | `"{job_id}"` | `iteration < 4` only |
| `reject_resume` | Reject | `"danger"` | `"{job_id}"` | Always |

When `iteration >= 4`, the Edit button is removed (block 4's "last edit" warning at `iteration == 3` plus the missing button is the only signal — no separate thread message). `route_feedback()` also hard-stops to `"reject"` at `iteration >= 4` regardless of feedback, as a safety net for stale views.

## Slack → Graph Action Mapping

Handled in `slack_handler.py` via `slack_bolt.App` action handlers.

| Trigger | `action_id` / event | Handler | `Command(resume=...)` |
|---------|--------------------|---------|-----------------------|
| Approve button | `approve_resume` | `handle_approve` | `"approve"` |
| Edit button | `edit_resume` | `handle_edit` | (waits for thread reply) |
| Reject button | `reject_resume` | `handle_reject` | `"reject"` |
| Thread message | `message.channels` event | `handle_message` | `"edit:<user text>"` |
| Startup sweep | `stale_sweep()` in `main.py` | direct `graph.invoke` | `"expired"` |

## Edit Text Capture Flow

The `edit_resume` action triggers a two-step interaction:

1. `handle_edit` fires → bot posts thread reply: `"What would you like to change?"` → stores `(thread_ts → job_id)` in `_pending_edit_registry`
2. User replies in thread → `handle_message` fires → pops registry → calls `graph.invoke(Command(resume=f"edit:{user_text}"), ...)`

## Expired Message

`stale_sweep()` calls `chat_update` on the original message:
```
text: "⏰ Expired – no action taken (24h passed)"
blocks: []   ← clears all blocks
```
