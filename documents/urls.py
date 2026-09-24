from django.urls import path
from . import views

urlpatterns = [
    # Stats
    path('stats/',                          views.document_stats,    name='document-stats'),

    # Documents
    path('',                                views.document_list,     name='document-list'),
    path('<int:pk>/',                       views.document_detail,   name='document-detail'),
    path('<int:pk>/versions/',              views.document_versions, name='document-versions'),

    # By matter
    path('matter/<int:matter_pk>/',         views.matter_documents,  name='matter-documents'),
]