from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document, DocumentVersion
from .serializers import (
    DocumentSerializer,
    DocumentCreateSerializer,
    DocumentUpdateSerializer,
    DocumentVersionSerializer,
    DocumentVersionUploadSerializer,
)


def paginate(queryset, request, serializer_class):
    try:
        page     = max(1, int(request.query_params.get('page', 1)))
        per_page = 25
    except ValueError:
        page, per_page = 1, 25
    start = (page - 1) * per_page
    end   = start + per_page
    total = queryset.count()
    return {
        'count':    total,
        'page':     page,
        'pages':    (total + per_page - 1) // per_page,
        'next':     page + 1 if end < total else None,
        'previous': page - 1 if page > 1 else None,
        'results':  serializer_class(queryset[start:end], many=True).data,
    }


def firm_documents(request):
    return (
        Document.objects
        .filter(firm=request.user.firm)
        .select_related('matter', 'uploaded_by')
        .prefetch_related('versions')
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def document_list(request):
    """
    GET  /api/v1/documents/
    POST /api/v1/documents/  (multipart/form-data)
    """
    if request.method == 'GET':
        qs = firm_documents(request)

        if matter_id := request.query_params.get('matter_id'):
            qs = qs.filter(matter_id=matter_id)
        if doc_type := request.query_params.get('doc_type'):
            qs = qs.filter(doc_type=doc_type)
        if search := request.query_params.get('search', '').strip():
            qs = qs.filter(title__icontains=search)

        return Response(paginate(qs, request, DocumentSerializer))

    # POST — multipart upload
    serializer = DocumentCreateSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    document = serializer.save()
    return Response(
        DocumentSerializer(document).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def document_detail(request, pk):
    """
    GET    /api/v1/documents/{id}/
    PATCH  /api/v1/documents/{id}/  — metadata only
    DELETE /api/v1/documents/{id}/
    """
    document = get_object_or_404(Document, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        return Response(DocumentSerializer(document).data)

    if request.method == 'PATCH':
        serializer = DocumentUpdateSerializer(
            document, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DocumentSerializer(document).data)

    # DELETE — remove document record and all versions
    document.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def document_versions(request, pk):
    """
    GET  /api/v1/documents/{id}/versions/  — list all versions
    POST /api/v1/documents/{id}/versions/  — upload new version
    """
    document = get_object_or_404(Document, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        versions = document.versions.select_related('uploaded_by').all()
        return Response({
            'document_id':    document.id,
            'title':          document.title,
            'version_count':  versions.count(),
            'versions':       DocumentVersionSerializer(versions, many=True).data,
        })

    # POST — upload new version
    serializer = DocumentVersionUploadSerializer(
        data=request.data,
        context={'request': request, 'document': document}
    )
    serializer.is_valid(raise_exception=True)
    version = serializer.save()
    return Response(
        DocumentVersionSerializer(version).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def matter_documents(request, matter_pk):
    """
    GET /api/v1/documents/matter/{matter_id}/
    Convenience endpoint — all documents for a specific matter.
    Dev C uses this to populate the matter detail document tab.
    """
    from matters.models import Matter
    matter = get_object_or_404(Matter, pk=matter_pk, firm=request.user.firm)
    qs     = Document.objects.filter(matter=matter).select_related(
               'uploaded_by'
             ).prefetch_related('versions')

    return Response({
        'matter':    {'id': matter.id, 'reference': matter.reference, 'title': matter.title},
        'count':     qs.count(),
        'documents': DocumentSerializer(qs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_stats(request):
    """
    GET /api/v1/documents/stats/
    Dashboard stats — total docs, by type, recent uploads.
    """
    from django.db.models import Count, Sum
    firm = request.user.firm

    docs     = Document.objects.filter(firm=firm)
    versions = DocumentVersion.objects.filter(document__firm=firm)

    by_type = (
        docs.values('doc_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    total_size = versions.aggregate(
        total=Sum('file_size')
    )['total'] or 0

    recent = docs.order_by('-created_at')[:5]

    return Response({
        'total_documents': docs.count(),
        'total_versions':  versions.count(),
        'total_size_mb':   round(total_size / (1024 * 1024), 2),
        'by_type':         list(by_type),
        'recent_uploads':  DocumentSerializer(recent, many=True).data,
    })