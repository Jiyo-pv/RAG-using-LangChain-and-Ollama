from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Document management
    path('documents/', views.document_list, name='document_list'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/delete/', views.delete_document, name='delete_document'),
    path('documents/<int:pk>/reindex/', views.reindex_document, name='reindex_document'),
    path('upload/', views.upload_document, name='upload'),

    # AI Chat & Conversations (Phase 5)
    path('chat/', views.chat_index, name='chat_index'),
    path('chat/start/', views.chat_index, name='chat'),  # Alias for backward-compatibility
    path('chat/new/', views.new_chat, name='new_chat'),
    path('chat/<int:conversation_id>/', views.chat_conversation, name='chat_conversation'),
    path('chat/<int:conversation_id>/send/', views.chat_send_message, name='chat_send_message'),
    path('chat/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),

    # Intelligence features (Phase 6, 7, 8)
    path('intelligence/summarization/', views.summarization_view, name='summarization'),
    path('intelligence/comparison/', views.comparison_view, name='comparison'),
    path('intelligence/research-analysis/', views.research_analysis_view, name='research_analysis'),
    path('intelligence/references/', views.reference_generator_view, name='reference_generator'),

    # Word export (.docx)
    path('reports/<int:report_id>/export-docx/', views.export_report_docx, name='export_report_docx'),

    # System & Settings
    path('settings/', views.settings_view, name='settings'),
]
