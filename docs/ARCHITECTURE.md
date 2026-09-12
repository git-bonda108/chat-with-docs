# Architecture

The entire system is one file, `rag-doc.py` (~130 lines). This document maps its components, the data flow between them, and the design trade-offs visible in the code.

## Component map

| Component | Location | Responsibility |
|---|---|---|
| `save_and_load_files()` | `rag-doc.py` | Writes each Streamlit upload to a `tempfile`, dispatches on extension to `PyPDFLoader`, `TextLoader`, or `UnstructuredWordDocumentLoader`, deletes the temp file, returns LangChain `Document`s. Unsupported extensions surface a `st.error` and are skipped. |
| `create_faiss_vectorstore()` | `rag-doc.py` | `FAISS.from_documents` over `OpenAIEmbeddings` — an in-memory index, no chunking step beyond what the loaders emit (typically one document per PDF page). |
| `summarize_text()` | `rag-doc.py` | Reads **all** raw documents back out of the FAISS docstore (`vectorstore.docstore._dict`), joins them into a single prompt, and calls `gpt-4o` once via the OpenAI SDK for a structured summary (Highlights / Key Takeaways / Actionable Insights). |
| `build_conversational_chain()` | `rag-doc.py` | `ConversationalRetrievalChain.from_llm` with `ChatOpenAI(model="gpt-4", temperature=0)`, the FAISS retriever at default settings, and `ConversationBufferMemory`. |
| Streamlit script body | `rag-doc.py` | UI and orchestration: file uploader, four labeled steps with spinners, a text input and Ask button for chat. |

## Data flow end to end

1. User uploads files → bytes land in Streamlit memory.
2. Each file round-trips through a temp file so the LangChain loaders (which take paths) can read it; temp files are unlinked immediately after.
3. Loader output (list of `Document`s) is embedded via the OpenAI embeddings API and indexed in FAISS, in process memory.
4. Summary stage: the full corpus text is concatenated and sent to `gpt-4o` in a single chat completion — retrieval is bypassed for summarization.
5. Chat stage: each question goes through the retrieval chain — question (plus buffered history) → FAISS similarity search → `gpt-4` answer → answer appended to memory.

## Orchestration analysis

Everything is **sequential and synchronous**. There is no parallelism, no async, no agent loop, no tool use, and no routing — a deliberate property of a minimal reference app. The only branching is the file-extension dispatch in the loader. Streamlit's rerun model is the de facto scheduler: the whole script re-executes top-to-bottom on every interaction.

## State and context engineering

- **Session state:** none is used. Because the pipeline results are not stored in `st.session_state`, every Streamlit rerun (including each press of the Ask button) rebuilds the vector store, regenerates the summary, and constructs a fresh chain — so the embedding and summary cost is paid repeatedly and chat memory does not actually survive across questions. This is the most consequential limitation in the file.
- **Chat context:** `ConversationBufferMemory` keeps the full unbounded history (within one script run) and `ConversationalRetrievalChain` uses it to condense follow-up questions before retrieval — standard LangChain behavior, no customization.
- **Summary context:** unbounded — the whole corpus goes into one prompt. Large uploads will exceed the model context window; there is no chunked/map-reduce fallback.

## Design decisions and trade-offs visible in the code

- **Two model paths:** the summary uses the OpenAI SDK directly (`gpt-4o`) while chat goes through LangChain (`gpt-4`). This keeps the summary prompt fully controlled at the cost of two client styles in one file.
- **FAISS in memory over a managed vector DB:** zero infrastructure, instant setup; the index dies with the process.
- **Temp-file round-trip for uploads:** accepts a small I/O cost to reuse battle-tested path-based loaders instead of parsing bytes manually.
- **Private-attribute access:** `vectorstore.docstore._dict` reaches into FAISS internals to enumerate documents — pragmatic, but coupled to the library's internals.
- **Legacy import paths:** loaders/embeddings/vectorstore are imported from `langchain.*` rather than `langchain_community.*` / `langchain_openai.*`; with unpinned requirements this is the most likely install-time breakage.

## Extending this system

Grounded next steps that the current shape makes natural:

1. **Cache pipeline state in `st.session_state`** (vector store, summary, chain). This is the highest-leverage change: it fixes repeated embedding cost and makes the buffer memory genuinely conversational across reruns, with no architectural change.
2. **Add an explicit chunking step** (`RecursiveCharacterTextSplitter`) between loading and embedding. Loaders currently emit page-sized documents; controlled chunk size and overlap would directly improve retrieval granularity.
3. **Replace the one-shot summary with a map-reduce summarization chain** over the already-loaded documents, removing the context-window ceiling — the documents are already enumerable from the docstore, so the seam exists.
4. **Migrate imports to the split LangChain packages and pin versions** (`langchain-community`, `langchain-openai` are already in requirements), turning the unpinned install from a hazard into a reproducible one.
5. **Persist the FAISS index to disk** (`FAISS.save_local` / `load_local`) keyed by a content hash of the uploads, so re-uploading the same corpus skips embedding entirely.
