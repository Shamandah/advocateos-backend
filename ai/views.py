from django.shortcuts import render
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from matters.models import Matter

from .models import AIConversation, AIInteraction, AICitation
from .serializers import LegalResearchSerializer
from .services.orchestrator import AIOrchestrator


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def legal_research(request):
    """
    POST /api/v1/ai/research/

    Perform source-grounded legal research.
    """

    serializer = LegalResearchSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    question = serializer.validated_data["question"]
    matter_id = serializer.validated_data.get("matter_id")

    matter = None

    if matter_id is not None:
        matter = get_object_or_404(
            Matter,
            pk=matter_id,
            firm=request.user.firm,
        )

    conversation = AIConversation.objects.create(
        firm=request.user.firm,
        user=request.user,
        matter=matter,
        title=question[:255],
    )

    from .models import AIMessage

    AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.USER,
        content=question,
    )

    orchestrator = AIOrchestrator()

    result = orchestrator.research(
        question,
        user=request.user,
        matter=matter,
    )

    interaction = AIInteraction.objects.create(
        firm=request.user.firm,
        user=request.user,
        conversation=conversation,
        matter=matter,
        operation_type=AIInteraction.OperationType.RESEARCH,
        provider=result["provider"],
        model_name=result["model"],
        success=True,
    )

    AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=result["answer"],
    )

    for source in result["sources"]:
        AICitation.objects.create(
            interaction=interaction,
            legal_document_id=source["document_id"],
            legal_chunk_id=source["chunk_id"],
            citation_text=(
                source["citation"]
                or source["title"]
            ),
            is_verified=False,
        )

    return Response(
        {
            "conversation_id": conversation.id,
            "interaction_id": interaction.id,
            "question": result["question"],
            "answer": result["answer"],
            "provider": result["provider"],
            "model": result["model"],
            "citations": [
                {
                    "document_id": source["document_id"],
                    "chunk_id": source["chunk_id"],
                    "title": source["title"],
                    "citation": source["citation"],
                    "source": source["source"],
                    "page_number": source["page_number"],
                }
                for source in result["sources"]
            ],
        },
        status=status.HTTP_200_OK,
    )
# Create your views here.
