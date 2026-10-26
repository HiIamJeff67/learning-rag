# Sources

This directory stores source material. Notes, worked examples, and failure write-ups go in `notebook/`.

## This chapter

| File | Source | Sections |
|---|---|---|
| `papers/lewis-2020-rag.pdf` | [arXiv:2005.11401v4](https://arxiv.org/abs/2005.11401) | Abstract, Section 1, Figure 1 |

Read those sections for three facts: what parametric memory is, what non-parametric memory is, and how the retriever passes text to the generator. The same points are in sections 2 and 3 of `notebook/IR Foundations and a Reproducible Naive RAG Baseline.md`.

Training hyperparameters, experiment tables, and the RAG-Sequence / RAG-Token split are covered with later chapters.

## Later reading

- [Sentence-Transformers quickstart](https://www.sbert.net/docs/quickstart.html): embedding as a function from text to a vector.
- [Stanford IR book: inverted index](https://nlp.stanford.edu/IR-book/html/htmledition/a-first-take-at-building-an-inverted-index-1.html): the data structure for keyword retrieval.
- [Stanford IR book: BM25](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html): sparse scoring beyond raw term count. Used with the hybrid-retrieval chapter.
- [HNSW paper](https://arxiv.org/abs/1603.09320): abstract only. An approximate nearest-neighbor index.

`papers/` holds author-distributed paper PDFs. Web pages and books stay as links.
