# Troubleshooting

## Bank-feed collision (duplicate transactions)
**Symptom:** reconciliation shows roughly double the expected number of unmatched
transactions, or the Transactions list shows exact-duplicate rows (same date, description,
amount) after a push.

**Cause:** if live bank-feed importing is turned on for a Wave account, Wave pulls in raw
transactions on its own schedule, independent of anything pushed through the API. If the
feed reaches a transaction before (or around the same time as) an API push for that same
period, both copies land. Sometimes Wave's own feed auto-categorizes its copy too, which
means the "filter to Uncategorized" trick won't reliably separate the two sets, since the
duplicate can already have a category on it.

**Fix:** before every push, delete everything in the Wave UI for the target account and
date range, not just Uncategorized rows, so there's nothing for the push to collide with.
See SKILL.md step 6.

**If it already happened:** the cleanest recovery is deleting every transaction for the
affected period (both the pushed copies and the feed-imported copies) and re-pushing clean.
That leads directly into the next issue below.

## externalId permanence
**Symptom:** after bulk-deleting transactions in the Wave UI and re-running the same push,
every single row fails with "externalId already exists", even though the UI confirms
the transactions are gone.

**Cause:** Wave does not free up a deleted transaction's externalId for reuse. The ID stays
"claimed" server-side permanently, regardless of whether the transaction itself still exists.

**Fix:** re-run with `--id-suffix <tag>` (e.g. `--id-suffix v2`) to mint fresh externalIds
for the redo. This is a normal, safe thing to do after a UI-side bulk delete, it's not
covering up a bug, it's just how Wave's ID namespace works.

## Timeout false-failures
**Symptom:** a push run gets killed partway through (shell timeout, network drop). On
resume, the very next row after the cutoff fails with "externalId already exists."

**Cause:** almost always, that row actually succeeded on Wave's side a moment before the
connection dropped, the process just never got to write "ok" to the log before it died.

**Fix:** check the Wave UI (search by date/amount/description) to confirm the transaction
is really there, then manually edit the log entry's `status` from `fail` to `ok` rather than
re-pushing. Don't do this blind, always confirm in the UI first.
