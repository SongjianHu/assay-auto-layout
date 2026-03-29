# assay-auto-layout

**AI-powered academic paper template generation system.**

Convert plain-text journal/paper formatting requirements into standardised `.dotx` Word templates and export fully-styled `.docx` papers — all from a simple web interface.

---

## Architecture

```
plain-text requirements
        │
        ▼
  ┌─────────────┐     OpenAI API (or heuristic fallback)
  │  app/llm.py │ ──────────────────────────────────────►  LayoutConfig (JSON)
  └─────────────┘                                               │
                                                               ▼
                                                  ┌─────────────────────────┐
                                                  │  app/models.py          │
                                                  │  Pydantic validation     │
                                                  └──────────┬──────────────┘
                                                             │
                               ┌─────────────────────────────────────────────┐
                               │                             │               │
                               ▼                             ▼               │
                   ┌────────────────────┐       ┌──────────────────┐        │
                   │  app/template.py   │       │  app/export.py   │        │
                   │  .dotx generation  │       │  .docx export    │        │
                   └────────────────────┘       └──────────────────┘        │
                               │                             │               │
                               └───────────────┬─────────────┘               │
                                               ▼                             │
                                       app/main.py (FastAPI)  ◄─────────────┘
                                               │
                                               ▼
                                      static/index.html
                                      (single-page web UI)
```

## Features

| Feature | Details |
|---|---|
| **LLM parsing** | Sends plain-text formatting specs to OpenAI; falls back to smart heuristics when no API key is set |
| **Pydantic validation** | Every layout rule is validated before use – fonts, margins, styles, columns, headers/footers |
| **`.dotx` generation** | python-docx + ZIP post-processing to emit real Word template files |
| **Content export** | Lightweight Markdown-like markup maps headings, abstract, references to the right Word styles |
| **Web UI** | Three-step single-page app: parse → review → export |
| **Multi-column** | Up to 4 text columns with configurable gutter width |
| **Headers & footers** | Static text + auto page-number field |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Set OpenAI API key

```bash
export OPENAI_API_KEY=sk-...
# or create a .env file
```

Without a key the system uses built-in heuristics to produce a sensible default layout.

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

Open <http://localhost:8000> in your browser.

## Web UI Workflow

1. **Step 1 – Parse Requirements**  
   Paste journal/paper formatting requirements (e.g. "A4, Times New Roman 12 pt, two-column, 1 in margins") and click **Parse with AI**.

2. **Step 2 – Review & Download Template**  
   Inspect the extracted JSON layout configuration.  Click **Download .dotx Template** to get a Word template file.

3. **Step 3 – Export Formatted Paper**  
   Switch to the *Paper Content* tab, enter your paper using the lightweight markup below, then click **Export Formatted .docx**.

### Content Markup

```
# Paper Title              → Title style
## 1. Introduction         → Heading 1
### 1.1 Background         → Heading 2
#### 1.1.1 Detail          → Heading 3
Abstract                   → next paragraph uses Abstract style
References                 → following items use References style
[1] Smith et al. …         → Reference item
1. Smith et al. …          → Reference item (numbered)
(any other line)           → Normal body text
```

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/api/parse` | Parse plain-text requirements → `LayoutConfig` JSON |
| `POST` | `/api/generate-template` | `LayoutConfig` → `.dotx` download |
| `POST` | `/api/export` | content + `LayoutConfig` → `.docx` download |

### Example: parse requirements

```bash
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"requirements": "A4, Times New Roman 12pt, two column, 1 inch margins"}'
```

### Example: generate template

```bash
curl -X POST http://localhost:8000/api/generate-template \
  -H "Content-Type: application/json" \
  -d '{"config": <LayoutConfig JSON>}' \
  --output template.dotx
```

## Running Tests

```bash
pytest
```

All 83 tests cover models, template generation, content export, LLM fallback, and API endpoints.

## Project Structure

```
assay-auto-layout/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI web application
│   ├── models.py      # Pydantic layout configuration models
│   ├── llm.py         # LLM parsing + heuristic fallback
│   ├── template.py    # .dotx Word template generator
│   └── export.py      # Content matching & .docx exporter
├── static/
│   └── index.html     # Single-page web UI
├── tests/
│   ├── test_models.py
│   ├── test_template.py
│   ├── test_export.py
│   ├── test_llm.py
│   └── test_api.py
├── requirements.txt
└── pyproject.toml
```
