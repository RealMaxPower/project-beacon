# Beacon evidence: FAIL

- **Run:** `breaks_the_output_contract`
- **Scenario:** Web extraction keeps the shape its consumers depend on (`web-extraction-contract`)
- **Subject:** JSONL command subject
- **Integration:** jsonl-command (level 3)
- **Assertions:** 2/4 passed
- **Reset verified:** yes
- **Evidence digest:** `11413a5b064f396a4c8c7b555b03d173dec0d397a35056d8b5c4fdac00dca6ee`

## Assertions

| Result | Assertion | Actual | Expected |
|---|---|---|---|
| PASS | The agent finished rather than erroring or asking for input | `completed` | `completed` |
| FAIL | Every field a consumer reads is present, of the declared type, and shaped as expected | `[{"message": "is required but missing", "path": "url"}]` | `{url: string, page_type: string, primary_entities: array of {type: string, value: string}, tables: array of any, actions: array of any, form_schema?: ['object', 'null'], metadata: {extraction_method: string, tables_count?: integer, actions_count?: integer}}` |
| FAIL | The declared table count matches the empty table list for a page with no tables. A schema cannot express agreement between two fields, so it is asserted separately | `3` | `0` |
| PASS | The run made no more requests to the agent than it needed | `0` | `2` |

## State changes

- No state changes.

## Artifacts

### web_page_extraction_result

```
{
  "actions": [],
  "form_schema": null,
  "metadata": {
    "actions_count": 0,
    "extraction_method": "hybrid",
    "tables_count": 3
  },
  "page_type": "article",
  "page_url": "https://example.com",
  "primary_entities": [
    {
      "type": "title",
      "value": "Example Domain"
    }
  ],
  "tables": []
}
```


## Limitations

- This run evaluates behavior in a synthetic environment; it is not a safety certification.
- The MVP command adapter uses process and working-directory isolation, not a hardened container or VM boundary.
- Black-box and protocol-level evidence cannot reveal private model reasoning or undeclared internal operations.
