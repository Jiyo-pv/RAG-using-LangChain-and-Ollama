"""
Document intelligence services:
- Summarization (Short, Detailed, Section-wise, Key Findings & Concepts)
- Research Paper Analysis (Problem, Objectives, Methodology, Dataset, Algorithms, Results, Limitations, Future Scope)
- Multi-document Comparison (Similarities, Differences, Methodologies, Findings with citations)
- Reference Generation (APA and IEEE styles strictly from document evidence)
"""

import logging
from typing import List, Tuple
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from .llm_service import get_llm

logger = logging.getLogger(__name__)


def extract_document_text(document, max_chars: int = 15000) -> str:
    """
    Extract readable text from a Document model file using PyMuPDF.
    Truncates to max_chars to stay within reasonable context window for local Qwen3.5:4b.
    """
    try:
        loader = PyMuPDFLoader(document.file.path)
        pages = loader.load()
        full_text = []
        for i, page in enumerate(pages):
            full_text.append(f"--- Page {i + 1} ---\n{page.page_content}")
        combined = "\n\n".join(full_text)
        if len(combined) > max_chars:
            return combined[:max_chars] + f"\n\n[... Remaining content truncated for performance; processed {len(pages)} pages ...]"
        return combined
    except Exception as exc:
        logger.error("Failed to extract text from %s: %s", document.title, exc)
        return ""


SUMMARIZE_SHORT_PROMPT = ChatPromptTemplate.from_template("""
You are an expert document intelligence assistant. Provide a clear, high-level executive summary (2-3 concise paragraphs) of the following document.
Focus strictly on the core theme, key insights, and main conclusions.
Do not invent facts.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT:
{content}

EXECUTIVE SHORT SUMMARY:
""")

SUMMARIZE_DETAILED_PROMPT = ChatPromptTemplate.from_template("""
You are an expert document intelligence assistant. Provide a comprehensive, detailed summary of the following document.
Structure your summary with:
1. Executive Overview
2. Main Arguments & Findings
3. Methodology / Implementation Details (if applicable)
4. Critical Outcomes & Conclusions

Do not invent facts. Stay grounded strictly in the text.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT:
{content}

DETAILED SUMMARY:
""")

SUMMARIZE_SECTIONS_PROMPT = ChatPromptTemplate.from_template("""
You are an expert document intelligence assistant. Analyze the document and provide a structured section-by-section breakdown.
For each major section or topic found in the text:
- Section Name / Topic
- Key Information & Concepts
- Main Takeaways

Do not invent facts.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT:
{content}

SECTION-WISE SUMMARY:
""")

SUMMARIZE_FINDINGS_PROMPT = ChatPromptTemplate.from_template("""
You are an expert document intelligence assistant. Extract and highlight the key findings and core concepts from this document.
Format your output as:
### Key Findings
- [List 5-8 major empirical, theoretical, or practical findings with supporting details from text]

### Important Concepts & Terminology
- **[Concept/Term]**: [Clear definition/explanation based on the text]

Do not invent facts.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT:
{content}

KEY FINDINGS & CONCEPTS:
""")

RESEARCH_ANALYSIS_PROMPT = ChatPromptTemplate.from_template("""
You are a senior academic peer reviewer and research analyst. Analyze the following research paper and extract its critical academic components in structured Markdown.

Analyze and present each section below:
### 1. Research Problem
(What specific problem or research gap does this paper address?)

### 2. Research Objectives
(What are the primary goals, hypotheses, or questions?)

### 3. Methodology
(What research design, framework, or experimental approach is used?)

### 4. Dataset
(What datasets, benchmarks, sample sizes, or data collection procedures were used? If not specified, state "Not specified in document".)

### 5. Algorithms & Models
(What algorithms, architectures, mathematical models, or tools are utilized?)

### 6. Results & Key Findings
(What quantitative or qualitative results were achieved?)

### 7. Limitations
(What weaknesses, constraints, or boundary conditions are acknowledged or apparent?)

### 8. Future Scope
(What directions for future research are proposed?)

RULES:
- Do not fabricate missing information. If a section is not mentioned in the paper, explicitly state: "Information not provided in the document."
- Ground every section in verifiable facts from the provided text.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT:
{content}

RESEARCH PAPER ANALYSIS:
""")

COMPARISON_PROMPT = ChatPromptTemplate.from_template("""
You are an expert document intelligence researcher. Compare and contrast the following documents.

DOCUMENTS PROVIDED:
{documents_text}

Provide an exhaustive, structured comparative analysis in Markdown:
### 1. Overview of Compared Documents
(Brief 1-2 sentence description of each document's subject matter)

### 2. Key Similarities
(Common themes, shared objectives, overlapping theories or findings with citations to document titles)

### 3. Key Differences
(Contrasting arguments, varying perspectives, or differing scopes with citations to document titles)

### 4. Methodology & Technical Comparison
(Compare datasets, algorithms, frameworks, or approaches used across the documents)

### 5. Comparative Findings & Outcomes
(How do their results compare? Which paper achieves what?)

### 6. Synthesis & Conclusion
(Consolidated insights drawn from comparing these works)

RULES:
- Always cite the document title when referencing a finding or method (e.g. "[Document: title]").
- Do not fabricate information. If a document does not address a topic, clearly state that.

COMPARATIVE ANALYSIS:
""")

REFERENCE_PROMPT = ChatPromptTemplate.from_template("""
You are an academic bibliographic citation specialist. Generate formal citations for the following document in both APA (7th Edition) and IEEE formats.

CRITICAL RULES:
1. ONLY use metadata and bibliographic details actually present in the provided document text (such as author names, publication year, title, journal/conference name, volume, issue, page numbers, DOI).
2. DO NOT fabricate or hallucinate missing authors, years, publishers, or titles.
3. If specific details (e.g., DOI or volume) are missing from the text, omit them in accordance with standard citation rules for incomplete data.

DOCUMENT TITLE: {title}
DOCUMENT EXCERPT (Title page / header / text):
{content}

Provide output formatted strictly as:

### APA Reference (7th Edition)
[APA formatted reference]

### IEEE Reference
[IEEE formatted reference]

### Bibliographic Details Extracted
- **Authors**: [Names found or "Not specified in document"]
- **Year**: [Year found or "n.d."]
- **Title**: [Title as stated]
- **Source / Publisher / Venue**: [Journal/Conference/Publisher or "Not specified"]
""")


def generate_summary(document, summary_type: str = 'summary_short') -> str:
    """Generate summary based on the requested type."""
    content = extract_document_text(document)
    if not content.strip():
        return "Unable to extract readable text from this document. Please ensure the PDF is not corrupted or scanned without OCR."

    llm = get_llm()
    prompt_map = {
        'summary_short': SUMMARIZE_SHORT_PROMPT,
        'summary_detailed': SUMMARIZE_DETAILED_PROMPT,
        'summary_sections': SUMMARIZE_SECTIONS_PROMPT,
        'summary_findings': SUMMARIZE_FINDINGS_PROMPT,
    }
    prompt = prompt_map.get(summary_type, SUMMARIZE_SHORT_PROMPT)
    chain = prompt | llm
    try:
        response = chain.invoke({"title": document.title, "content": content})
        return response.content
    except Exception as exc:
        logger.exception("Summarization failed for %s", document.title)
        return f"⚠️ Error generating summary: {exc}. Please verify Ollama is running."


def generate_research_analysis(document) -> str:
    """Generate comprehensive research paper analysis."""
    content = extract_document_text(document, max_chars=18000)
    if not content.strip():
        return "Unable to extract readable text from this document."

    llm = get_llm()
    chain = RESEARCH_ANALYSIS_PROMPT | llm
    try:
        response = chain.invoke({"title": document.title, "content": content})
        return response.content
    except Exception as exc:
        logger.exception("Research analysis failed for %s", document.title)
        return f"⚠️ Error generating research analysis: {exc}. Please verify Ollama is running."


def generate_comparison(documents: list) -> str:
    """Compare multiple documents."""
    if len(documents) < 2:
        return "At least two documents are required for comparison."

    combined_texts = []
    # Distribute character limit among documents
    per_doc_limit = max(4000, 16000 // len(documents))
    for i, doc in enumerate(documents, start=1):
        txt = extract_document_text(doc, max_chars=per_doc_limit)
        combined_texts.append(f"=== DOCUMENT {i}: '{doc.title}' (File: {doc.original_filename or doc.title}) ===\n{txt}")

    full_context = "\n\n".join(combined_texts)
    llm = get_llm()
    chain = COMPARISON_PROMPT | llm
    try:
        response = chain.invoke({"documents_text": full_context})
        return response.content
    except Exception as exc:
        logger.exception("Comparison failed")
        return f"⚠️ Error comparing documents: {exc}. Please verify Ollama is running."


def generate_reference(document) -> str:
    """Generate APA and IEEE references from document evidence."""
    # Use the first 2-3 pages where title, author, and publication info usually reside
    content = extract_document_text(document, max_chars=6000)
    if not content.strip():
        return "Unable to extract readable text from this document."

    llm = get_llm()
    chain = REFERENCE_PROMPT | llm
    try:
        response = chain.invoke({"title": document.title, "content": content})
        return response.content
    except Exception as exc:
        logger.exception("Reference generation failed for %s", document.title)
        return f"⚠️ Error generating references: {exc}. Please verify Ollama is running."
