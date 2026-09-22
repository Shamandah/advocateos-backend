from django.urls import path
from . import views

urlpatterns = [
    # Clients
    path('clients/',              views.client_list,        name='client-list'),
    path('clients/<int:pk>/',     views.client_detail,      name='client-detail'),

    # Matters
    path('matters/',              views.matter_list,        name='matter-list'),
    path('matters/<int:pk>/',     views.matter_detail,      name='matter-detail'),

    # Notes
    path('matters/<int:pk>/notes/',                    views.matter_notes,       name='matter-notes'),
    path('matters/<int:pk>/notes/<int:note_pk>/',      views.matter_note_detail, name='matter-note-detail'),
]