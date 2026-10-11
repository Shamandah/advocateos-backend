
from django.conf import settings
from django.db import models


class LegalSource(models.Model):
    """
    A source of Kenyan legal knowledge.

    Examples:
    - Kenya Law
    - Laws of Kenya
    - Supreme Court
    - Court of Appeal
    - High Court
    - Practice Directions
    - Bench Books
    """

    class SourceType(models.TextChoices):
        CASE_LAW = "case_law", "Case Law"
        LEGISLATION = "legislation", "Legislation"
        PRACTICE_DIRECTION = "practice_direction", "Practice Direction"
        BENCH_BOOK = "bench_book", "Bench Book"
        REGULATION = "regulation", "Regulation"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255)
    source_type = models.CharField(
        max_length=30,
        choices=SourceType.choices,
    )
    publisher = models.CharField(max_length=255, blank=True)
    base_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class LegalDocument(models.Model):
    """
    A specific legal document belonging to a LegalSource.

    This is PUBLIC/LEGAL KNOWLEDGE.
    It is deliberately separate from documents.Document,
    which stores a firm's private matter documents.
    """

    source = models.ForeignKey(
        LegalSource,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    title = models.CharField(max_length=500)

    citation = models.CharField(
        max_length=500,
        blank=True,
        help_text="Official legal citation, case citation, or statute reference.",
    )

    document_type = models.CharField(
        max_length=30,
        choices=LegalSource.SourceType.choices,
    )

    court = models.CharField(max_length=255, blank=True)
    judicial_officer = models.CharField(max_length=255, blank=True)

    case_number = models.CharField(max_length=255, blank=True)

    date_published = models.DateField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    url = models.URLField(blank=True)

    content = models.TextField()

    checksum = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Content checksum used to detect duplicate/changed documents.",
    )

    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the document has been verified against its authoritative source.",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-date_published", "title"]


class LegalChunk(models.Model):
    """
    A searchable section of a LegalDocument.

    Chunks are the basic retrieval unit for RAG.
    """

    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    chunk_index = models.PositiveIntegerField()

    content = models.TextField()

    heading = models.CharField(
        max_length=500,
        blank=True,
    )

    page_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    start_char = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    end_char = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # Reserved for vector search once PostgreSQL + pgvector is introduced.
    embedding = models.JSONField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document.title} — chunk {self.chunk_index}"

    class Meta:
        ordering = ["document", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_legal_chunk_per_document",
            )
        ]


class AIConversation(models.Model):
    """
    A conversation between an AdvocateOS user and the AI.

    Conversations are tenant-scoped to a Firm.
    A Matter is optional because some legal research is
    unrelated to a specific client matter.
    """

    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )

    matter = models.ForeignKey(
        "matters.Matter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )

    title = models.CharField(
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"AI Conversation #{self.pk}"

    class Meta:
        ordering = ["-updated_at"]


class AIMessage(models.Model):
    """
    Individual message within an AI conversation.
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AIInteraction(models.Model):
    """
    Audit record for an AI operation.

    Stores metadata about what the AI did without making the
    model provider itself part of AdvocateOS's core architecture.
    """

    class OperationType(models.TextChoices):
        RESEARCH = "research", "Legal Research"
        ANALYZE_MATTER = "analyze_matter", "Matter Analysis"
        ANALYZE_DOCUMENT = "analyze_document", "Document Analysis"
        SUMMARIZE = "summarize", "Summarization"
        DRAFT = "draft", "Document Drafting"
        CHAT = "chat", "AI Chat"

    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="ai_interactions",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ai_interactions",
    )

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interactions",
    )

    matter = models.ForeignKey(
        "matters.Matter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_interactions",
    )

    operation_type = models.CharField(
        max_length=30,
        choices=OperationType.choices,
    )

    provider = models.CharField(
        max_length=100,
        blank=True,
    )

    model_name = models.CharField(
        max_length=150,
        blank=True,
    )

    prompt_tokens = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    completion_tokens = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    latency_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    success = models.BooleanField(default=True)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AICitation(models.Model):
    """
    Records the legal sources used to support an AI response.
    """

    interaction = models.ForeignKey(
        AIInteraction,
        on_delete=models.CASCADE,
        related_name="citations",
    )

    legal_document = models.ForeignKey(
        LegalDocument,
        on_delete=models.PROTECT,
        related_name="ai_citations",
    )

    legal_chunk = models.ForeignKey(
        LegalChunk,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ai_citations",
    )

    citation_text = models.CharField(
        max_length=1000,
    )

    relevance_score = models.FloatField(
        null=True,
        blank=True,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
# Create your models here.
