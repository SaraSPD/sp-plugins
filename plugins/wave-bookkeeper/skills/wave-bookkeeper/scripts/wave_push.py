#!/usr/bin/env python3
"""Push categorized transactions to Wave.

Usage (run from the project root -- the folder with wave-token.txt / wave-ids.json):
  python3 scripts/wave_push.py 2026-03 checking "Business Checking"                 # DRY RUN
  python3 scripts/wave_push.py 2026-03 checking "Business Checking" --push           # real push
  python3 scripts/wave_push.py 2026-03 cc "Business CC" --review Categorized-cc.csv  # custom review file
  python3 scripts/wave_push.py 2026-03 checking "Business Checking" --push --id-suffix v2
      # mint fresh externalIds -- use this if you're redoing a push after the user
      # bulk-deleted the originals in the Wave UI. Wave never frees up a deleted
      # transaction's externalId, so retrying with the original IDs will fail every
      # row with "externalId already exists" even though the UI shows them gone.

Reads:  <month>/<raw>.csv              (source of truth -- descriptions pushed VERBATIM from here)
        <month>/<review file>          (categories only; defaults to Categorized-<raw>.csv)
        wave-ids.json, wave-token.txt  (project root)
Writes: <month>/push-log-<raw>.json    (per-row results; makes re-runs resume, never duplicate)

Safety: validates every row pairing (date, amount, description modulo whitespace)
before anything is sent. Any mismatch = abort with zero pushes.
Rows categorized "SKIP..." (e.g. SKIP - Transfer) are validated but never pushed --
used for the far side of a transfer pair that Wave will auto-create once the other
side is converted to a real Transfer in the UI (see references/troubleshooting.md).
"""
import csv
import json
import re
import sys
from pathlib import Path
from wave_api import gql_raw, HERE  # sits alongside this file

# Review categories that map to a different Wave account than their own display name.
# Add entries here for anything that should land in a holding account until the user
# (or browser automation) converts it to a real Transfer in the Wave UI -- e.g.:
#   "TRANSFER -> Business Credit Card": "Uncategorized Expense",
CATEGORY_ALIASES = {}

# Raw CSVs use different column names depending on source (bank export vs card export).
# Each tuple tried in order; first key found in the row wins. Add more if a new bank's
# export uses different headers.
DATE_KEYS = ["DATE", "Post Date", "Date"]
DESC_KEYS = ["DESCRIPTION", "Description"]
AMOUNT_KEYS = ["AMOUNT", "Amount"]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def pick(row, keys):
    for k in keys:
        if k in row:
            return row[k]
    raise KeyError(f"none of {keys} found in row columns {list(row.keys())}")


def main():
    review_file = None
    if "--review" in sys.argv:
        idx = sys.argv.index("--review")
        review_file = sys.argv[idx + 1]

    id_suffix = ""
    if "--id-suffix" in sys.argv:
        idx = sys.argv.index("--id-suffix")
        id_suffix = "-" + sys.argv[idx + 1]

    skip_next = False
    args = []
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in ("--review", "--id-suffix"):
            skip_next = True
            continue
        if a.startswith("--"):
            continue
        args.append(a)
    if len(args) != 3:
        sys.exit(__doc__)
    month, raw_name, anchor_name = args
    do_push = "--push" in sys.argv
    if review_file is None:
        review_file = f"Categorized-{raw_name}.csv"

    mdir = HERE / month
    raw_rows = list(csv.DictReader(open(mdir / f"{raw_name}.csv")))
    rev_rows = list(csv.reader(open(mdir / review_file)))[1:]  # Date,Description,Amount,Category,Flag,Note

    ids = json.loads((HERE / "wave-ids.json").read_text())
    accounts = {a["name"]: a for a in ids["accounts"] if not a["isArchived"]}
    if anchor_name not in accounts:
        sys.exit(f"ABORT: anchor account '{anchor_name}' not in wave-ids.json")

    # ---- validation gate: nothing is pushed unless EVERY row passes ----
    if len(raw_rows) != len(rev_rows):
        sys.exit(f"ABORT: row count mismatch raw={len(raw_rows)} review={len(rev_rows)}")
    plan, problems, skipped = [], [], 0
    for i, (r, v) in enumerate(zip(raw_rows, rev_rows)):
        vdate, vdesc, vamt, vcat = v[0], v[1], v[2], v[3]
        rdate, rdesc, ramt = pick(r, DATE_KEYS), pick(r, DESC_KEYS), pick(r, AMOUNT_KEYS)
        if rdate != vdate:
            problems.append(f"row {i+1}: date {rdate} != {vdate}")
        if abs(float(ramt) - float(vamt)) > 0.004:
            problems.append(f"row {i+1}: amount {ramt} != {vamt}")
        if norm(rdesc) != norm(vdesc):
            problems.append(f"row {i+1}: description mismatch")
        if vcat.upper().startswith("SKIP"):
            skipped += 1
            continue
        cat = CATEGORY_ALIASES.get(vcat, vcat)
        acct = accounts.get(cat)
        if not acct:
            problems.append(f"row {i+1}: category '{cat}' not found in Wave accounts")
            continue
        amt = float(ramt)
        mm, dd, yyyy = rdate.split("/")
        plan.append({
            "row": i + 1,
            "date": f"{yyyy}-{mm}-{dd}",
            "description": rdesc,       # VERBATIM from raw file
            "amount": abs(amt),
            "direction": "DEPOSIT" if amt > 0 else "WITHDRAWAL",
            "category": cat,
            "category_id": acct["id"],
            # liability line on a withdrawal = paying it down = DECREASE; everything else INCREASE
            "balance": "DECREASE" if (acct["type"]["value"] == "LIABILITY" and amt < 0) else "INCREASE",
            "external_id": f"{raw_name}-{month}-r{i+1:03d}{id_suffix}",
        })
    if problems:
        sys.exit("ABORT -- validation failed, nothing pushed:\n  " + "\n  ".join(problems))

    from collections import Counter
    counts = Counter(p["category"] for p in plan)
    print(f"Validated {len(plan)} rows OK ({skipped} SKIP rows excluded from push). Category totals:")
    for c, n in counts.most_common():
        print(f"  {n:3d}  {c}")

    if not do_push:
        print("\nDRY RUN -- nothing pushed. Re-run with --push to execute.")
        return

    log_file = mdir / f"push-log-{raw_name}.json"
    log = json.loads(log_file.read_text()) if log_file.exists() else {}
    mutation = """mutation ($input: MoneyTransactionCreateInput!) {
      moneyTransactionCreate(input: $input) {
        didSucceed inputErrors { path message code } transaction { id }
      }
    }"""
    anchor_id = accounts[anchor_name]["id"]
    ok = fail = skip = 0
    for p in plan:
        key = p["external_id"]
        if log.get(key, {}).get("status") == "ok":
            skip += 1
            continue
        out = gql_raw(mutation, {"input": {
            "businessId": ids["business"]["id"],
            "externalId": key,
            "date": p["date"],
            "description": p["description"],
            "anchor": {"accountId": anchor_id, "amount": p["amount"], "direction": p["direction"]},
            "lineItems": [{"accountId": p["category_id"], "amount": p["amount"], "balance": p["balance"]}],
        }})
        res = (out.get("data") or {}).get("moneyTransactionCreate") or {}
        if res.get("didSucceed"):
            log[key] = {"status": "ok", "id": res["transaction"]["id"], "row": p["row"]}
            ok += 1
        else:
            err = res.get("inputErrors") or out.get("errors")
            log[key] = {"status": "fail", "error": str(err)[:300], "row": p["row"]}
            fail += 1
            print(f"  row {p['row']} FAILED: {str(err)[:160]}")
        log_file.write_text(json.dumps(log, indent=2))
    print(f"\nDone: {ok} pushed, {skip} skipped (already pushed), {fail} failed.")
    if fail:
        print("Fix and re-run -- successes won't be re-pushed.")


if __name__ == "__main__":
    main()
