---
name: wave-bookkeeper
description: Turns raw bank/credit-card CSV exports into categorized transactions and pushes them live to Wave Accounting via its GraphQL API, with a resumable push log so nothing ever gets double-pushed. Use this skill whenever the user names a bookkeeping period to process for a Wave-based business, "do March", "let's start on June", "categorize the Q2 statements", "push April to Wave", "reconcile Business Checking", or asks to resolve flagged/uncategorized transactions, convert credit-card-payment placeholders into real Wave transfers, or set up recurring monthly bookkeeping for a small business on Wave. Do NOT trigger this for businesses that don't use Wave, or for one-off questions about a single transaction that don't involve the CSV-to-Wave pipeline.
---

# Wave Bookkeeper

Imports a month (or any period) of raw bank CSV exports into categorized, validated transactions live in Wave Accounting, safely, resumably, and without ever guessing at a category it hasn't seen precedent for.

## Why this exists

Running monthly bookkeeping for a small business by hand in Wave using its UI is slow and tedious manual work. This skill's design is built entirely around fixing that by pushing transactions to an accounting ledger via API after they have been categorized with AI.

**Never process a period the user hasn't named.** Don't infer "this must mean last month", if it's ambiguous, ask which period.

## The workflow

### 0. Find the standing-rules file first
Before anything else, look in the project root for a markdown file that functions as a running log of categorization rules and per-period status, this is the project's memory. It might be named `bookkeeping-rules.md`, or it might already exist under a different name (e.g. `PROJECT-INSTRUCTIONS.md`) if the business had a bookkeeping process going before this skill was added. Whatever it's called, that's the file to read before categorizing and append to whenever the user gives a new rule, don't create a second one alongside it. Only create `bookkeeping-rules.md` from `assets/bookkeeping-rules-template.md` if no such file exists yet.

### 1. Getting started (first time only)
If this is a new business/project, you'll need three things in the project root before anything else works:
- `wave-token.txt`, a Wave API token (see `references/wave-api-setup.md` for how to generate one)
- `wave-ids.json`, the business ID and every account's Wave ID/type, bootstrapped once via a small script (also in `references/wave-api-setup.md`)
- `chart-of-accounts.csv`, the exact account names as they appear in Wave (copy from `assets/chart-of-accounts-template.csv` and fill in)

### 2. Getting the CSVs
The user can drop bank/CC CSV exports directly in the project root, or in subfolders if they prefer, either is fine, and if they ask you to sort files into subfolders, do that. Don't require a specific structure; just find the files for the period the user named.

### 3. Categorize
Read `chart-of-accounts.csv` and the standing-rules file (see step 0) first. Then build (or reuse/extend) a categorization script following the pattern in `references/categorization-pattern.md`: a chain of vendor/description pattern rules, each mapping to an exact account name from the chart of accounts, checked in order from most-specific to most-general. Anything that doesn't match a known pattern gets **flagged, not guessed**, flag ambiguous vendors, new vendors with no precedent, and anything where two categories are plausible.

Write the result to `Categorized-<account>.csv` (e.g. `Categorized-checking.csv`), every row gets Date, Description, Amount, Category, Flag, Note. Never rename or reword the Description column; it has to match the raw CSV verbatim for the push validation step to work.

### 4. Report back, briefly
Tell the user in chat: how many transactions, how many categorized automatically, how many flagged and why (one line each). Keep it short, a few sentences and a short list, not a essay. They can see the full detail in the CSV itself if they want it.

### 5. Let the user correct
The user can fix anything either directly in the `Categorized-*.csv` file, or just by telling you in chat ("that Amazon charge is Supplies, not Office Expense"). Either way, apply the fix and, if it's a pattern that'll recur, add it to the standing-rules file so you don't have to be told twice.

### 6. Before pushing: clear out Wave's own bank feed
If the Wave account you're about to push into has live bank-feed importing turned on, Wave may have **already auto-imported these same transactions on its own**, independent of anything you push via the API. If both copies land, you get exact duplicates, same date, description, and amount, sometimes even sharing the same category because Wave's feed can auto-categorize too. This is the single biggest failure mode of this whole pipeline (see `references/troubleshooting.md` for what it looks like when it happens).

So before every push, ask the user if that is the case in their Wave Accounting setup, and if so tell the user: go to Transactions in Wave, select the account, set the date range to the period you're about to push, select all, and **delete everything for that period**, not just the ones marked Uncategorized, since a feed-imported duplicate can already carry a category and slip past that filter. Wait for their go-ahead before pushing.

### 7. Push
Use `scripts/wave_push.py`. Always dry-run first (no `--push` flag), it validates every row's date/amount/description against the raw CSV and aborts with zero pushes if anything doesn't match. Only pass `--push` once the dry run looks right. The script writes a log file after every successful row, so if it gets interrupted, re-running just picks up where it left off, it will never push the same row twice.

If a push run gets killed by a timeout partway through, the *next* row often fails with "external ID already exists", that almost always means the previous row actually succeeded server-side right before the connection dropped, not a real duplicate. Check the Wave UI to confirm, then correct the log entry from `fail` to `ok` rather than re-running blind. Full detail in `references/troubleshooting.md`.

### 8. Transfers need the user (or browser automation), not the API
Wave's public API has no clean way to create a true Transfer between two accounts. So any row that represents one side of a transfer (a credit-card payment showing up on both the checking and the CC statement) gets pushed as a placeholder, categorized to Uncategorized Expense, rather than guessed at.

Converting these into real Transfers has to happen in the Wave UI: click the transaction's Category cell, choose "Transfer to Bank, Credit Card, or Loan," then either pick the matching existing transaction on the other account (if one exists) or create a fresh transfer leg (if the billing cycles don't line up yet). If you have browser automation available, tell the user first that you're about to open Wave and click through the UI to convert these, so they know what's happening and aren't caught off guard by their browser moving on its own, then walk through it. If you don't have browser automation available, tell the user exactly which transactions need this and let them know why it can't be done through the API.

### 9. Reconcile
Once transfers are converted, reconcile the account against the bank statement (beginning/ending balance, deposits, withdrawals). If you have browser automation available, tell the user first that you're about to open Wave's reconciliation screen and work through it, so they know what's happening, then walk through it, cross-checking against the statement PDF first if you have it so you can tell them what to expect. If you don't have browser automation available, walk the user through the reconciliation screen themselves instead.

### 10. Wrap up
Give a short final summary: what got pushed, what's reconciled, what's still flagged and needs a decision, any new rules you added to the standing-rules file. Keep it tight, a handful of lines, not a report.

## Flexibility

The user might say "do March," "let's start March," "categorize the March statements", any of these mean the same thing. Don't require exact phrasing; if the intent is clearly "process this period," proceed.

## Files in this skill
- `scripts/wave_api.py`, GraphQL request helper (token/endpoint handling)
- `scripts/wave_push.py`, validate → dry-run → push → resumable log
- `references/wave-api-setup.md`, generating a Wave API token and bootstrapping `wave-ids.json`
- `references/categorization-pattern.md`, the rule-chain-with-flag-fallback pattern for categorization scripts
- `references/troubleshooting.md`, bank-feed collisions, externalId permanence, timeout false-failures
- `assets/chart-of-accounts-template.csv`, starting point for a business's chart of accounts
- `assets/bookkeeping-rules-template.md`, starting point for the standing-rules file
