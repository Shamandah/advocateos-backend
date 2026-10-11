from django.urls import path

from .views import legal_research


urlpatterns = [
    path("research/", legal_research, name="legal-research"),
]