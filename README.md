# sp-plugins

A Claude Code / Claude Cowork plugin marketplace.

## wave-bookkeeper

Imports raw bank/credit-card CSV exports into categorized, validated transactions
live in Wave Accounting, safely, and without ever guessing at a category it
hasn't seen precedent for.

This grew out of a real, recurring problem: running monthly bookkeeping for a small business
by hand in Wave using its UI is slow and tedious manual work. The plugin's design is built
entirely around that constraint by pushing transactions to an accounting ledger via API after
they have been categorized with AI.

**Design decisions, and why:**

- **Validate before anything is sent.** Every row's date, amount, and description are checked
  against the source CSV before a single API call is made. Any mismatch aborts the whole run
  with zero pushes, no partial, inconsistent state.
- **Idempotent, resumable pushes.** Each transaction gets a deterministic external ID and a
  per-row log is written after every success. If a push gets killed mid-run (network drop,
  timeout), re-running picks up exactly where it left off and never double-pushes.
- **Flag, don't guess.** Ambiguous vendors and anything without a clear categorization
  precedent get flagged for human review rather than silently assigned a best-guess category.
  A wrong category costs far more than a five-second human decision, it can go unnoticed for
  months.
- **Know what the API can't do, and say so.** Wave's public API has no clean way to create a
  true account-to-account Transfer. Rather than hack around that with a wrong category, the
  plugin pushes a clearly-labeled placeholder and tells the user exactly which UI action
  converts it, instead of quietly producing incorrect books.
- **A growing memory, not a static config.** Categorization rules accumulate in a
  business-specific rules file that the workflow reads before every run and appends to
  whenever the user corrects something, so the same mistake is never explained twice.

This shape, validate → dry-run → act → resumable log, with a human in the loop exactly where
judgment is genuinely required, is the same pattern worth reaching for in any workflow that
writes to an external system of record.

See [`plugins/wave-bookkeeper/skills/wave-bookkeeper/SKILL.md`](plugins/wave-bookkeeper/skills/wave-bookkeeper/SKILL.md)
for the full workflow, and `references/troubleshooting.md` for real failure modes this design
was hardened against (bank-feed duplicate collisions, an accounting API's non-obvious ID-reuse
behavior, timeout false-failures).

## Install

```
/plugin marketplace add sara-perjalian/sp-plugins
/plugin install wave-bookkeeper@sp-plugins
```

(Replace `sara-perjalian/sp-plugins` with wherever this repo ends up living on GitHub.)

## Repo layout

```
sp-plugins/
├── .claude-plugin/
│   └── marketplace.json          # marketplace catalog
└── plugins/
    └── wave-bookkeeper/
        ├── .claude-plugin/
        │   └── plugin.json       # plugin manifest
        └── skills/
            └── wave-bookkeeper/
                ├── SKILL.md
                ├── scripts/       # wave_api.py, wave_push.py
                ├── references/    # setup, categorization pattern, troubleshooting
                └── assets/        # chart-of-accounts + rules-file templates
```
