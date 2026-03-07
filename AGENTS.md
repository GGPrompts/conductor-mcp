# Agent Instructions

This project uses **ggbd** (beads) for issue tracking with a shared Supabase/Postgres backend.

## Quick Reference

```bash
ggbd ready              # Find available work
ggbd show <id>          # View issue details
ggbd update <id> --status in_progress  # Claim work
ggbd close <id>         # Complete work
# Supabase auto-syncs (no manual sync needed)
```

## Landing The Plane (When Shipping)

Only do this workflow when asked to land changes (commit/push), or when finishing a change that should clearly be published.

1. File ggbd issues for follow-ups (only if needed)
2. Run relevant quality gates (tests/linters/build) if applicable
3. Update/close ggbd issue(s) if used
4. Publish:
   ```bash
   git pull --rebase
   git push
   git status  # should show "up to date with origin"
   ```
5. Hand off: brief context for next session

If not shipping, leave a clear handoff summary instead.
