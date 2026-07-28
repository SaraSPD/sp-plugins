# The categorization pattern: rule chain with a flag fallback

There's no bundled categorization script, on purpose, the rules are entirely specific to
each business's vendors and chart of accounts. Instead, write (or extend) a script following
this pattern for each business, and let it grow over time as `bookkeeping-rules.md` grows.

## The shape

For each row in the raw CSV, walk an ordered chain of pattern checks. The first match wins.
Order matters: put narrow/specific patterns before broad ones, or a broad pattern will
swallow rows that should have matched something more specific later in the chain.

```python
def categorize(date, desc, amount):
    d = desc.upper()

    # --- narrow, high-confidence matches first ---
    if "DISCOVER" in d and "E-PAYMENT" in d:
        return ("Credit Card Payments", None, "precedent")

    if "ZELLE" in d and "ACME PLUMBING" in d:
        return ("Repairs & Maintenance", None, "precedent: Acme Plumbing -> R&M")

    # --- broader vendor-family buckets ---
    if any(g in d for g in ["CHEVRON", "SHELL", "TEXACO", "76 "]):
        return ("Travel & Transportation", None, "gas station brand bucket")

    # --- transfer placeholders (see references/troubleshooting.md) ---
    if "CREDIT CRD" in d and "AUTOPAY" in d:
        return ("TRANSFER -> Business Credit Card", "TRANSFER", "CC payment, needs manual transfer conversion")

    # --- nothing matched: flag, don't guess ---
    return ("Uncategorized Expense", "FLAG", "new vendor, no precedent")
```

## Why flag instead of guess

A wrong category costs the user more than a flagged row, flagged rows get caught and fixed
before anything is pushed; a wrong guess might sail through undetected for months. When a
vendor is genuinely ambiguous (could plausibly be two different accounts), flag it and say
why, rather than picking one.

## Where the rules come from
- `bookkeeping-rules.md`, accumulated standing rules from past corrections
- The chart of accounts itself, for exact category name spelling
- Direct precedent: if the same vendor was categorized a specific way in a previous month
  without the user flagging it as wrong, treat that as confirmed and reuse it

## After building the categorized CSV
Bugs in the rule chain are easiest to catch by re-reading the rules for ordering conflicts
(a broad rule accidentally firing before a narrow one) before handing the CSV to the user,
this has been the single most common bug in practice.
