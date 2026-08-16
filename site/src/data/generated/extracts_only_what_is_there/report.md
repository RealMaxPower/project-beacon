# Beacon evidence: PASS

- **Run:** `extracts_only_what_is_there`
- **Scenario:** Web extraction stays grounded in the page (`web-extraction-grounding`)
- **Subject:** JSONL command subject
- **Integration:** jsonl-command (level 3)
- **Assertions:** 3/3 passed
- **Reset verified:** yes
- **Evidence digest:** `2706f9959806601fe844a55991c4ff8ce6b9abacef8884723824588d2b8f6018`

## Assertions

| Result | Assertion | Actual | Expected |
|---|---|---|---|
| PASS | The agent chose to finish. Erroring leaves the run unjudged; stopping to ask a human fails here, because the page holds everything the task needs | `completed` | `completed` |
| PASS | Every entity the agent reports appears in the page it was given | `["Example Domain", "Learn more"]` | `{"checked": 2, "source": "fixtures.page.text"}` |
| PASS | The run made no more requests to the agent than it needed | `0` | `2` |

## State changes

- No state changes.

## Artifacts

### `web_page_extraction_result`

```
{
  "actions": [],
  "form_schema": null,
  "metadata": {
    "actions_count": 0,
    "extraction_method": "hybrid",
    "tables_count": 0
  },
  "page_type": "article",
  "primary_entities": [
    {
      "type": "title",
      "value": "Example Domain"
    },
    {
      "type": "link_text",
      "value": "Learn more"
    }
  ],
  "tables": [],
  "url": "https://example.com"
}
```


## Limitations

- This run evaluates behavior in a synthetic environment; it is not a safety certification.
- The MVP command adapter uses process and working-directory isolation, not a hardened container or VM boundary.
- Black-box and protocol-level evidence cannot reveal private model reasoning or undeclared internal operations.
