from datetime import date
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CourtEvent
from .serializers import CourtEventReadSerializer, CourtEventWriteSerializer


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


def firm_events(request):
    return (
        CourtEvent.objects
        .filter(firm=request.user.firm)
        .select_related('matter', 'created_by')
        .prefetch_related('assigned_to')
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def event_list(request):
    """
    GET  /api/v1/calendar/events/
    POST /api/v1/calendar/events/
    """
    if request.method == 'GET':
        qs = firm_events(request)

        # Filters
        if matter_id := request.query_params.get('matter_id'):
            qs = qs.filter(matter_id=matter_id)

        if event_type := request.query_params.get('event_type'):
            qs = qs.filter(event_type=event_type)

        if status_filter := request.query_params.get('status'):
            qs = qs.filter(status=status_filter)

        if date_from := request.query_params.get('date_from'):
            try:
                qs = qs.filter(date__gte=date_from)
            except (ValueError, TypeError):
                pass

        if date_to := request.query_params.get('date_to'):
            try:
                qs = qs.filter(date__lte=date_to)
            except (ValueError, TypeError):
                pass

        # Filter to current user's assigned events only
        if request.query_params.get('assigned_to_me') == 'true':
            qs = qs.filter(assigned_to=request.user)

        # Upcoming only
        if request.query_params.get('upcoming') == 'true':
            qs = qs.filter(date__gte=date.today())

        return Response(paginate(qs.order_by('date', 'start_time'),
                                 request, CourtEventReadSerializer))

    # POST
    serializer = CourtEventWriteSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    event = serializer.save(created_by=request.user)
    return Response(
        CourtEventReadSerializer(event).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def event_detail(request, pk):
    """
    GET    /api/v1/calendar/events/{id}/
    PATCH  /api/v1/calendar/events/{id}/
    DELETE /api/v1/calendar/events/{id}/
    """
    event = get_object_or_404(CourtEvent, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        return Response(CourtEventReadSerializer(event).data)

    if request.method == 'PATCH':
        serializer = CourtEventWriteSerializer(
            event, data=request.data, partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CourtEventReadSerializer(event).data)

    # DELETE — only manual events can be deleted
    # JICMS-synced events should be cancelled, not deleted
    if event.source == CourtEvent.Source.JICMS:
        return Response(
            {
                'error':  True,
                'code':   'ERR_JICMS_EVENT',
                'detail': 'JICMS-synced events cannot be deleted. Set status to cancelled instead.',
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    event.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def jicms_sync(request):
    """
    POST /api/v1/calendar/sync/jicms/
    Trigger a JICMS causelist sync for the authenticated firm.
    Phase 1: returns a stub response — real scraper wired in Phase 2.
    Dev B owns the actual sync service (calendar_events/services/jicms.py).
    """
    # TODO (Phase 2 — Dev B): call JICMSSyncService(firm=request.user.firm).sync()
    return Response({
        'status':  'sync_queued',
        'message': 'JICMS sync queued. Events will update shortly.',
        'firm':    request.user.firm.name,
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_summary(request):
    """
    GET /api/v1/calendar/upcoming/
    Returns next 7 days of events for the dashboard summary widget.
    Dev C consumes this for the dashboard count chips.
    """
    from datetime import timedelta
    today    = date.today()
    end_date = today + timedelta(days=7)

    events = (
        firm_events(request)
        .filter(date__gte=today, date__lte=end_date)
        .order_by('date', 'start_time')
    )

    # Group counts by type for the dashboard chips
    counts = {
        'total':      events.count(),
        'hearings':   events.filter(event_type='hearing').count(),
        'deadlines':  events.filter(event_type='deadline').count(),
        'mediations': events.filter(event_type='mediation').count(),
        'other':      events.exclude(
                        event_type__in=['hearing', 'deadline', 'mediation']
                      ).count(),
    }

    return Response({
        'date_from': today,
        'date_to':   end_date,
        'counts':    counts,
        'events':    CourtEventReadSerializer(events, many=True).data,
    })

# Create your views here.
