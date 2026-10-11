from django.urls import path

from . import views

urlpatterns = [
    path("", views.template_list, name="template-list"),
    path("<int:pk>/", views.template_detail, name="template-detail"),
    path(
        "<int:pk>/versions/",
        views.template_versions,
        name="template-versions",
    ),
    path(
        "versions/<int:version_pk>/variables/",
        views.template_version_variables,
        name="template-version-variables",
    ),
    path(
        "versions/<int:version_pk>/clauses/",
        views.template_version_clauses,
        name="template-version-clauses",
    ),
]
