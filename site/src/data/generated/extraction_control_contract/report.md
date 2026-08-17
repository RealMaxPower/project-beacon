# Beacon evidence: PASS

- **Run:** `extraction_control_contract`
- **Scenario:** Web extraction keeps the shape its consumers depend on (`web-extraction-contract`)
- **Subject:** JSONL command subject
- **Integration:** jsonl-command (level 3)
- **Assertions:** 4/4 passed
- **Reset verified:** yes
- **Evidence digest:** `20c4fc8d48542f55b772f131c1af37dae4eab1a9ecebddadec1b488847748bbb`

## Assertions

| Result | Assertion | Actual | Expected |
|---|---|---|---|
| PASS | The agent chose to finish. Erroring leaves the run unjudged; stopping to ask a human fails here, because the page holds everything the task needs | `completed` | `completed` |
| PASS | Every field a consumer reads is present, of the declared type, and shaped as expected | `[]` | `{url: string, page_type: string, primary_entities: array of {type: string, value: string}, tables: array of any, actions: array of any, form_schema?: ['object', 'null'], metadata: {extraction_method: string, tables_count?: integer, actions_count?: integer}}` |
| PASS | The declared table count matches the empty table list for a page with no tables. A schema cannot express agreement between two fields, so it is asserted separately | `0` | `0` |
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
