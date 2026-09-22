from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Client, Matter, MatterNote
from .serializers import (
    ClientSerializer, ClientWriteSerializer,
    MatterListSerializer, MatterDetailSerializer,
    MatterWriteSerializer, MatterNoteSerializer,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def paginate(queryset, request, serializer_class):
    """Simple page-based pagination matching CONTRACTS.md envelope."""
    try:
        page     = max(1, int(request.query_params.get('page', 1)))
        per_page = 25
    except ValueError:
        page, per_page = 1, 25
    start = (page - 1) * per_page
    end   = start + per_page
    total = queryset.count()
    data  = serializer_class(queryset[start:end], many=True).data
    return {
        'count':    total,
        'page':     page,
        'pages':    (total + per_page - 1) // per_page,
        'next':     page + 1 if end < total else None,
        'previous': page - 1 if page > 1 else None,
        'results':  data,
    }


def firm_clients(request):
    return Client.objects.filter(firm=request.user.firm)


def firm_matters(request):
    return Matter.objects.filter(firm=request.user.firm).select_related(
        'client', 'lead_attorney', 'created_by'
    ).prefetch_related('team')


# ─── Client views ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_list(request):
    """
    GET  /api/v1/clients/ — list firm's clients (search, filter, paginate)
    POST /api/v1/clients/ — create a new client
    """
    if request.method == 'GET':
        qs = firm_clients(request)

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(email__icontains=search)

        is_company = request.query_params.get('is_company')
        if is_company is not None:
            qs = qs.filter(is_company=is_company.lower() == 'true')

        return Response(paginate(qs.order_by('name'), request, ClientSerializer))

    # POST
    serializer = ClientWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    client = serializer.save(firm=request.user.firm, created_by=request.user)
    return Response(ClientSerializer(client).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def client_detail(request, pk):
    """
    GET    /api/v1/clients/{id}/
    PATCH  /api/v1/clients/{id}/
    DELETE /api/v1/clients/{id}/
    """
    client = get_object_or_404(Client, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        return Response(ClientSerializer(client).data)

    if request.method == 'PATCH':
        serializer = ClientWriteSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ClientSerializer(client).data)

    # DELETE — only if no matters attached
    if client.matters.exists():
        return Response(
            {'error': True, 'code': 'ERR_HAS_MATTERS',
             'detail': 'Cannot delete a client with existing matters. Archive the matters first.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    client.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Matter views ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def matter_list(request):
    """
    GET  /api/v1/matters/
    POST /api/v1/matters/
    """
    if request.method == 'GET':
        qs = firm_matters(request)

        # Filters
        if status_filter := request.query_params.get('status'):
            qs = qs.filter(status=status_filter)
        if area := request.query_params.get('practice_area'):
            qs = qs.filter(practice_area=area)
        if client_id := request.query_params.get('client_id'):
            qs = qs.filter(client_id=client_id)
        if attorney_id := request.query_params.get('lead_attorney_id'):
            qs = qs.filter(lead_attorney_id=attorney_id)
        if search := request.query_params.get('search', '').strip():
            qs = qs.filter(title__icontains=search) | qs.filter(reference__icontains=search)

        return Response(paginate(qs, request, MatterListSerializer))

    # POST
    serializer = MatterWriteSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    matter = serializer.save(firm=request.user.firm, created_by=request.user)
    return Response(MatterDetailSerializer(matter).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def matter_detail(request, pk):
    """
    GET    /api/v1/matters/{id}/
    PATCH  /api/v1/matters/{id}/
    DELETE /api/v1/matters/{id}/
    """
    matter = get_object_or_404(Matter, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        return Response(MatterDetailSerializer(matter).data)

    if request.method == 'PATCH':
        serializer = MatterWriteSerializer(
            matter, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MatterDetailSerializer(matter).data)

    # DELETE — only archived matters can be deleted
    if matter.status != Matter.Status.ARCHIVED:
        return Response(
            {'error': True, 'code': 'ERR_NOT_ARCHIVED',
             'detail': 'Only archived matters can be deleted. Set status to archived first.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    matter.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Matter notes ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def matter_notes(request, pk):
    """
    GET  /api/v1/matters/{id}/notes/
    POST /api/v1/matters/{id}/notes/
    """
    matter = get_object_or_404(Matter, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        notes = matter.notes.select_related('author').all()
        return Response(paginate(notes, request, MatterNoteSerializer))

    serializer = MatterNoteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    note = serializer.save(matter=matter, author=request.user)
    return Response(MatterNoteSerializer(note).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def matter_note_detail(request, pk, note_pk):
    """
    PATCH  /api/v1/matters/{id}/notes/{note_id}/
    DELETE /api/v1/matters/{id}/notes/{note_id}/
    """
    matter = get_object_or_404(Matter, pk=pk, firm=request.user.firm)
    note   = get_object_or_404(MatterNote, pk=note_pk, matter=matter)

    # Only the note author can edit or delete it
    if note.author != request.user:
        return Response(
            {'error': True, 'code': 'ERR_PERMISSION_DENIED',
             'detail': 'You can only edit or delete your own notes.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'PATCH':
        serializer = MatterNoteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MatterNoteSerializer(note).data)

    note.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

# Create your views here.
