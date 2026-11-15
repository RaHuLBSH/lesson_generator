# Curated reference: Retrieval-Augmented Generation

Retrieval-Augmented Generation (RAG) combines information retrieval with text generation. A system first searches a collection of documents for information relevant to a question. It then supplies the retrieved text to a language model, which uses that context to form an answer. This can make answers more relevant to a private or changing information collection and can make their sources easier to inspect.

A typical flow is: prepare and split documents into smaller passages; represent passages for search (often as numerical embeddings); retrieve relevant passages for a user's question; give the question and passages to a language model; return an answer, ideally with source references. RAG can still fail when documents are missing, retrieval finds the wrong passages, or the model misreads its context. It does not guarantee truth.
