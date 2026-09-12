# Evaluation

## What exists today

**No automated tests exist in this repository.** There is no test file, no CI configuration, and no metrics recorded anywhere in code or docs. Any quality claim about this app beyond "it runs" would be unverifiable, so none is made.

### Edge cases the code visibly handles

Enumerated from `rag-doc.py`, not imagined:

- **Missing API key:** startup raises `ValueError` with a clear message if `OPENAI_API_KEY` is unset.
- **Unsupported file extension:** shows `st.error(...)` and skips the file rather than crashing; processing continues with the remaining files.
- **All uploads invalid / nothing loaded:** an empty document list is caught (`st.error("No valid documents loaded.")`) before the embedding stage.
- **Temp file cleanup:** uploaded files are unlinked immediately after loading.

### Edge cases the code does not handle

- No timeouts, retries, or error handling around OpenAI API calls (embeddings, summary, chat) — a network or quota failure surfaces as a raw Streamlit exception.
- No guard on corpus size before the one-shot summary prompt; oversized uploads will fail at the model context window.
- No handling for scanned/image-only PDFs (loader returns empty text silently).
- No input validation on the question field (an empty question is sent to the chain as-is).

## Proposed evaluation harness

None of the following exists; this is the design the system should grow into.

### Golden dataset shape

A small checked-in corpus under `eval/fixtures/` (2–3 short PDFs/TXTs with known content) plus `eval/golden.jsonl`, one record per case:

```json
{"question": "...", "expected_facts": ["..."], "source_file": "fixture-a.pdf"}
```

### Layers

1. **Deterministic unit tests (pytest):** `save_and_load_files` extension dispatch and skip behavior; empty-corpus guard; a fake-embeddings FAISS round-trip so retrieval logic is tested without network.
2. **Retrieval evaluation:** for each golden question, assert the source chunk appears in the top-k retrieved documents (hit-rate gate, e.g. ≥ 0.9 on the fixture set).
3. **Answer evaluation:** LLM-as-judge scoring of groundedness (answer supported by retrieved context) and fact coverage against `expected_facts`; report mean scores per run.
4. **Summary evaluation:** assert the structured sections (Highlights / Key Takeaways / Actionable Insights) are present and that no summary sentence contradicts the fixtures (judge-scored).

### Gates

- Unit tests: hard gate, must pass.
- Retrieval hit-rate and groundedness: threshold gates that block merges when they regress below the recorded baseline.
- Cost/latency per golden run recorded as informational metrics, not gates.

Until such a harness lands, treat every behavioral claim about this app as manually verified at best.
