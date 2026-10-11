from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Template, TemplateVersion
from .serializers import (
    TemplateSerializer,
    TemplateCreateSerializer,
    TemplateVersionSerializer,
    TemplateVersionCreateSerializer,
    TemplateVariableSerializer,
    TemplateClauseSerializer,
)


def visible_templates(user):
    """
    A user may see active system templates and templates owned by
    their own firm. A missing firm never grants access to firm data.
    """
    qs = Template.objects.all()

    if not getattr(user, "firm_id", None):
        return qs.filter(
            is_system_template=True,
            owner_firm__isnull=True,
            is_active=True,
        )

    return qs.filter(
        Q(owner_firm_id=user.firm_id, is_active=True)
        | Q(
            is_system_template=True,
            owner_firm__isnull=True,
            is_active=True,
        )
    ).distinct()


def visible_template_versions(user):
    return TemplateVersion.objects.filter(
        template__in=visible_templates(user)
    ).select_related("template", "created_by", "approved_by")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def template_list(request):
    """
    GET  /api/v1/templates/
    POST /api/v1/templates/
    """
    if request.method == "GET":
        qs = visible_templates(request.user).select_related("owner_firm")

        if category := request.query_params.get("category"):
            qs = qs.filter(category=category)

        if search := request.query_params.get("search", "").strip():
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(document_type__icontains=search)
                | Q(description__icontains=search)
            )

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        per_page = 25
        start = (page - 1) * per_page
        total = qs.count()

        return Response({
            "count": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
            "next": page + 1 if start + per_page < total else None,
            "previous": page - 1 if page > 1 else None,
            "results": TemplateSerializer(
                qs[start:start + per_page], many=True
            ).data,
        })

    serializer = TemplateCreateSerializer(
        data=request.data,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)

    try:
        template = serializer.save()
    except IntegrityError:
        return Response(
            {
                "error": True,
                "code": "TEMPLATE_SLUG_CONFLICT",
                "detail": "A template with this slug already exists for your firm.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        TemplateSerializer(template).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def template_detail(request, pk):
    template = get_object_or_404(visible_templates(request.user), pk=pk)
    return Response(TemplateSerializer(template).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def template_versions(request, pk):
    """
    GET  /api/v1/templates/<id>/versions/
    POST /api/v1/templates/<id>/versions/
    """
    template = get_object_or_404(visible_templates(request.user), pk=pk)

    if request.method == "GET":
        versions = template.versions.select_related(
            "created_by", "approved_by"
        ).all()
        return Response({
            "template_id": template.id,
            "template_name": template.name,
            "count": versions.count(),
            "versions": TemplateVersionSerializer(
                versions, many=True
            ).data,
        })

    # System templates are read-only through the ordinary firm API.
    if template.is_system_template or template.owner_firm_id != getattr(
        request.user, "firm_id", None
    ):
        return Response(
            {
                "error": True,
                "code": "TEMPLATE_READ_ONLY",
                "detail": "You cannot create versions of this template.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = TemplateVersionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        with transaction.atomic():
            latest = template.versions.aggregate(
                highest=Max("version_number")
            )["highest"] or 0

            version = TemplateVersion.objects.create(
                template=template,
                version_number=latest + 1,
                status="draft",
                renderer=serializer.validated_data["renderer"],
                change_summary=serializer.validated_data["change_summary"],
                created_by=request.user,
            )
    except IntegrityError:
        return Response(
            {
                "error": True,
                "code": "TEMPLATE_VERSION_CONFLICT",
                "detail": "A concurrent version creation caused a conflict. Please retry.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        TemplateVersionSerializer(version).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def template_version_variables(request, version_pk):
    version = get_object_or_404(
        visible_template_versions(request.user),
        pk=version_pk,
    )
    variables = version.variables.all()

    return Response({
        "template_version_id": version.id,
        "count": variables.count(),
        "results": TemplateVariableSerializer(variables, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def template_version_clauses(request, version_pk):
    version = get_object_or_404(
        visible_template_versions(request.user),
        pk=version_pk,
    )
    clauses = version.clauses.all()

    return Response({
        "template_version_id": version.id,
        "count": clauses.count(),
        "results": TemplateClauseSerializer(clauses, many=True).data,
    })
