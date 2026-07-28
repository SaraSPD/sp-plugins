# Setting up Wave API access for a new business

Do this once per business, before the first "do [month]" run.

## 1. Generate an API token
In Wave: **Settings → API Tokens** → create a new full-access token for the business.
Save it as `wave-token.txt` in the project root, just the raw token string, nothing else.
This file is a live credential: keep it out of any git repo (add it to `.gitignore`), and
never print its contents in chat or logs.

## 2. Bootstrap wave-ids.json
Wave's GraphQL mutations need the business ID and every account's internal ID + type, not
their display names. Fetch these once with a small script:

```python
import json
from wave_api import gql_raw

query = """
{
  businesses(page: 1, pageSize: 1) {
    edges { node {
      id
      accounts(page: 1, pageSize: 200) {
        edges { node { id name isArchived type { value } } }
      }
    }}
  }
}
"""
out = gql_raw(query)
biz = out["data"]["businesses"]["edges"][0]["node"]
result = {
    "business": {"id": biz["id"]},
    "accounts": [e["node"] for e in biz["accounts"]["edges"]],
}
with open("wave-ids.json", "w") as f:
    json.dump(result, f, indent=2)
print(f"Wrote {len(result['accounts'])} accounts to wave-ids.json")
```

Run this from the project root (same folder as `wave-token.txt`). Re-run it any time the
chart of accounts changes in Wave (new account added, renamed, archived), `wave_push.py`
looks up accounts by exact name, so a stale `wave-ids.json` will cause "category not found"
errors.

## 3. Fill in chart-of-accounts.csv
Copy `assets/chart-of-accounts-template.csv` into the project root and list every account
name exactly as it appears in Wave, this is what the categorization script checks against,
so exact spelling/capitalization matters.

## 4. Standing-rules file
Check the project root for an existing standing-rules file first, a business that had
bookkeeping going before this skill was added may already have one under a different name
(e.g. `PROJECT-INSTRUCTIONS.md`). If one exists, keep using it as-is; don't create a second
one. Only if none exists, copy `assets/bookkeeping-rules-template.md` into the project root
as `bookkeeping-rules.md`. Either way, this file is where standing categorization rules
accumulate over time as the user corrects things, treat it as the skill's memory for this
specific business.
