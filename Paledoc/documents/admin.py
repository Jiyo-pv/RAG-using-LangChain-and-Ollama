from django.contrib import admin
from .models import Document, Conversation, Message, AnalysisReport


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'status', 'page_count', 'file_size', 'uploaded_at')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('title', 'original_filename', 'user__username')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'user__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'conversation__title')


@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'user', 'created_at')
    list_filter = ('report_type', 'created_at')
    search_fields = ('title', 'content', 'user__username')
