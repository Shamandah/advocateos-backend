from ai.models import LegalChunk


def search_legal_knowledge(query, *, limit=8):
    """
    Initial legal knowledge retrieval.

    Phase 1 uses simple PostgreSQL/SQLite-compatible text matching.
    Later this will become hybrid retrieval:

        keyword search
        +
        vector similarity
        +
        metadata filtering
        +
        reranking
    """

    query = query.strip()

    if not query:
        return []

    terms = [
        term.strip()
        for term in query.split()
        if len(term.strip()) >= 3
    ]

    if not terms:
        return []

    queryset = (
        LegalChunk.objects
        .filter(
            document__is_active=True,
            document__source__is_active=True,
        )
        .select_related("document", "document__source")
    )

    # Simple initial retrieval.
    # We deliberately keep this database-compatible before
    # introducing PostgreSQL-specific full-text/vector search.
    from django.db.models import Q

    condition = Q()

    for term in terms[:10]:
        condition |= Q(content__icontains=term)
        condition |= Q(heading__icontains=term)
        condition |= Q(document__title__icontains=term)
        condition |= Q(document__citation__icontains=term)

    chunks = queryset.filter(condition)[:limit]

    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "title": chunk.document.title,
            "citation": chunk.document.citation,
            "source": chunk.document.source.name,
            "content": chunk.content,
            "page_number": chunk.page_number,
        }
        for chunk in chunks
    ]