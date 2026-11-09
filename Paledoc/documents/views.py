import json
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import DocumentForm
from .models import AnalysisReport, Conversation, Document, Message
from .services.export_service import create_docx_report
from .services.intelligence_service import (
    generate_comparison,
    generate_reference,
    generate_research_analysis,
    generate_summary,
)
from .services.pdf_processor import delete_document_vectors, process_and_index_document
from .services.rag_service import ask_paledoc

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------------------
@login_required
def dashboard(request):
    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')
    doc_count = documents.count()
    completed_count = documents.filter(status='completed').count()
    conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')
    reports = AnalysisReport.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'documents/dashboard.html', {
        'documents': documents,
        'doc_count': doc_count,
        'completed_count': completed_count,
        'conv_count': conversations.count(),
        'report_count': reports.count(),
        'recent_documents': documents[:5],
        'recent_conversations': conversations[:4],
        'recent_reports': reports[:4],
    })


# -----------------------------------------------------------------------------
# DOCUMENT MANAGEMENT
# -----------------------------------------------------------------------------
@login_required
def upload_document(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.original_filename = request.FILES['file'].name
            document.file_size = request.FILES['file'].size
            document.status = 'processing'
            document.save()

            try:
                chunk_count = process_and_index_document(document)
                from langchain_community.document_loaders import PyMuPDFLoader
                raw = PyMuPDFLoader(document.file.path).load()
                document.page_count = len(raw)
                document.status = 'completed'
                document.save(update_fields=['status', 'page_count'])
                messages.success(request, f'"{document.title}" successfully indexed ({chunk_count} chunks across {document.page_count} pages).')
                logger.info("Document %d indexed successfully (%d chunks).", document.id, chunk_count)
            except Exception as exc:
                logger.exception("Failed to process document %d: %s", document.id, exc)
                document.status = 'failed'
                document.save(update_fields=['status'])
                messages.error(request, f'Upload succeeded but vector indexing failed: {exc}')

            return redirect('document_list')
    else:
        form = DocumentForm()

    return render(request, 'documents/upload.html', {'form': form})


@login_required
def document_list(request):
    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'documents/document_list.html', {'documents': documents})


@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    return render(request, 'documents/document_detail.html', {'document': document})


@login_required
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == 'POST':
        title = document.title
        try:
            delete_document_vectors(document.id)
        except Exception as exc:
            logger.warning("Could not delete vectors for document %d: %s", document.id, exc)
        try:
            document.file.delete(save=False)
        except Exception as exc:
            logger.warning("Could not delete file for document %d: %s", document.id, exc)
        document.delete()
        messages.success(request, f'Document "{title}" and all its vector embeddings were deleted.')
        return redirect('document_list')
    return render(request, 'documents/document_confirm_delete.html', {'document': document})


@login_required
def reindex_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            delete_document_vectors(document.id)
        except Exception:
            pass
        document.status = 'processing'
        document.save(update_fields=['status'])
        try:
            chunk_count = process_and_index_document(document)
            from langchain_community.document_loaders import PyMuPDFLoader
            raw = PyMuPDFLoader(document.file.path).load()
            document.page_count = len(raw)
            document.status = 'completed'
            document.save(update_fields=['status', 'page_count'])
            messages.success(request, f'Re-indexed "{document.title}" ({chunk_count} chunks).')
        except Exception as exc:
            logger.exception("Re-index failed for document %d: %s", document.id, exc)
            document.status = 'failed'
            document.save(update_fields=['status'])
            messages.error(request, f'Re-indexing failed: {exc}')
    return redirect('document_list')


# -----------------------------------------------------------------------------
# PERSISTENT AI CHAT & CONVERSATIONS
# -----------------------------------------------------------------------------
@login_required
def chat_index(request):
    """List conversations or redirect to the most recent one; if none exist, create one."""
    latest_conv = Conversation.objects.filter(user=request.user).first()
    if latest_conv:
        return redirect('chat_conversation', conversation_id=latest_conv.id)
    return redirect('new_chat')


@login_required
def new_chat(request):
    """Create a new conversation, optionally pre-selecting completed documents."""
    conv = Conversation.objects.create(
        user=request.user,
        title="New Chat",
    )
    # By default, attach all completed user documents
    completed_docs = Document.objects.filter(user=request.user, status='completed')
    if completed_docs.exists():
        conv.documents.set(completed_docs)
    return redirect('chat_conversation', conversation_id=conv.id)


@login_required
def chat_conversation(request, conversation_id):
    """Interactive chat with message history, document selection, and citations."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    conversations = Conversation.objects.filter(user=request.user)
    user_documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')

    # Update selected documents if form submitted
    if request.method == 'POST' and 'update_documents' in request.POST:
        selected_ids = request.POST.getlist('doc_ids')
        valid_docs = Document.objects.filter(id__in=selected_ids, user=request.user, status='completed')
        conversation.documents.set(valid_docs)
        messages.success(request, f"Updated active documents ({valid_docs.count()} selected).")
        return redirect('chat_conversation', conversation_id=conversation.id)

    messages_list = conversation.messages.all()

    return render(request, 'documents/chat.html', {
        'conversation': conversation,
        'conversations': conversations,
        'user_documents': user_documents,
        'messages_list': messages_list,
        'active_doc_ids': list(conversation.documents.values_list('id', flat=True)),
    })


@login_required
@require_POST
def chat_send_message(request, conversation_id):
    """Handle sending a question in a conversation, either via AJAX or POST."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if is_ajax and request.body:
        try:
            data = json.loads(request.body)
            question = data.get('question', '').strip()
        except Exception:
            question = request.POST.get('question', '').strip()
    else:
        question = request.POST.get('question', '').strip()

    if not question:
        if is_ajax:
            return JsonResponse({'error': 'Question cannot be empty.'}, status=400)
        return redirect('chat_conversation', conversation_id=conversation.id)

    # If conversation title is default, set title to first question excerpt
    if conversation.title == 'New Chat' or not conversation.title:
        conversation.title = question[:45] + ("..." if len(question) > 45 else "")
        conversation.save(update_fields=['title', 'updated_at'])

    # Save user message
    user_msg = Message.objects.create(
        conversation=conversation,
        role='user',
        content=question,
    )

    # Get conversation history for context
    history_entries = []
    for msg in conversation.messages.exclude(id=user_msg.id).order_by('created_at'):
        history_entries.append({'role': msg.role, 'content': msg.content})

    # Get active document IDs (server-side verification)
    active_doc_ids = list(conversation.documents.values_list('id', flat=True))

    # Run hybrid RAG
    answer_text, source_docs = ask_paledoc(
        question=question,
        user_id=request.user.id,
        doc_ids=active_doc_ids if active_doc_ids else None,
        history=history_entries,
    )

    # Format sources for persistence
    sources_data = []
    for doc in source_docs:
        sources_data.append({
            'filename': doc.metadata.get('filename') or doc.metadata.get('source', 'Unknown'),
            'page': int(doc.metadata.get('page', 0)) + 1,
            'excerpt': doc.page_content[:280] + ("..." if len(doc.page_content) > 280 else ""),
        })

    # Save assistant message
    asst_msg = Message.objects.create(
        conversation=conversation,
        role='assistant',
        content=answer_text,
        sources=sources_data,
    )

    # Touch conversation updated_at
    conversation.save(update_fields=['updated_at'])

    if is_ajax:
        return JsonResponse({
            'success': True,
            'user_message': {
                'id': user_msg.id,
                'content': user_msg.content,
                'created_at': user_msg.created_at.strftime('%I:%M %p'),
            },
            'assistant_message': {
                'id': asst_msg.id,
                'content': asst_msg.content,
                'sources': sources_data,
                'created_at': asst_msg.created_at.strftime('%I:%M %p'),
            },
        })

    return redirect('chat_conversation', conversation_id=conversation.id)


@login_required
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    if request.method == 'POST':
        conversation.delete()
        messages.success(request, "Conversation deleted.")
        return redirect('chat_index')
    return redirect('chat_conversation', conversation_id=conversation.id)


# -----------------------------------------------------------------------------
# SUMMARIZATION
# -----------------------------------------------------------------------------
@login_required
def summarization_view(request):
    user_documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')
    result_text = None
    selected_doc = None
    summary_type = 'summary_short'
    report_id = None

    if request.method == 'POST':
        doc_id = request.POST.get('document_id')
        summary_type = request.POST.get('summary_type', 'summary_short')

        if doc_id:
            selected_doc = get_object_or_404(Document, id=doc_id, user=request.user, status='completed')
            result_text = generate_summary(selected_doc, summary_type=summary_type)

            # Save report
            type_labels = dict(AnalysisReport.REPORT_TYPES)
            label = type_labels.get(summary_type, 'Summary')
            report = AnalysisReport.objects.create(
                user=request.user,
                title=f"{label} — {selected_doc.title}",
                report_type=summary_type,
                content=result_text,
            )
            report.documents.add(selected_doc)
            report_id = report.id

    return render(request, 'documents/summarization.html', {
        'user_documents': user_documents,
        'result_text': result_text,
        'selected_doc': selected_doc,
        'summary_type': summary_type,
        'report_id': report_id,
    })


# -----------------------------------------------------------------------------
# MULTI-DOCUMENT COMPARISON
# -----------------------------------------------------------------------------
@login_required
def comparison_view(request):
    user_documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')
    result_text = None
    selected_doc_ids = []
    report_id = None

    if request.method == 'POST':
        selected_doc_ids = request.POST.getlist('doc_ids')
        docs = list(Document.objects.filter(id__in=selected_doc_ids, user=request.user, status='completed'))

        if len(docs) < 2:
            messages.warning(request, "Please select at least 2 documents to compare.")
        else:
            result_text = generate_comparison(docs)
            titles = ", ".join([d.title for d in docs])
            report = AnalysisReport.objects.create(
                user=request.user,
                title=f"Comparison: {titles[:80]}",
                report_type='comparison',
                content=result_text,
            )
            report.documents.set(docs)
            report_id = report.id

    return render(request, 'documents/comparison.html', {
        'user_documents': user_documents,
        'result_text': result_text,
        'selected_doc_ids': [str(d) for d in selected_doc_ids],
        'report_id': report_id,
    })


# -----------------------------------------------------------------------------
# RESEARCH PAPER ANALYSIS
# -----------------------------------------------------------------------------
@login_required
def research_analysis_view(request):
    user_documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')
    result_text = None
    selected_doc = None
    report_id = None

    if request.method == 'POST':
        doc_id = request.POST.get('document_id')
        if doc_id:
            selected_doc = get_object_or_404(Document, id=doc_id, user=request.user, status='completed')
            result_text = generate_research_analysis(selected_doc)

            report = AnalysisReport.objects.create(
                user=request.user,
                title=f"Research Analysis — {selected_doc.title}",
                report_type='research_analysis',
                content=result_text,
            )
            report.documents.add(selected_doc)
            report_id = report.id

    return render(request, 'documents/research_analysis.html', {
        'user_documents': user_documents,
        'result_text': result_text,
        'selected_doc': selected_doc,
        'report_id': report_id,
    })


# -----------------------------------------------------------------------------
# REFERENCE GENERATOR (APA & IEEE)
# -----------------------------------------------------------------------------
@login_required
def reference_generator_view(request):
    user_documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')
    result_text = None
    selected_doc = None
    report_id = None

    if request.method == 'POST':
        doc_id = request.POST.get('document_id')
        if doc_id:
            selected_doc = get_object_or_404(Document, id=doc_id, user=request.user, status='completed')
            result_text = generate_reference(selected_doc)

            report = AnalysisReport.objects.create(
                user=request.user,
                title=f"Citations — {selected_doc.title}",
                report_type='citation_apa',
                content=result_text,
            )
            report.documents.add(selected_doc)
            report_id = report.id

    return render(request, 'documents/reference_generator.html', {
        'user_documents': user_documents,
        'result_text': result_text,
        'selected_doc': selected_doc,
        'report_id': report_id,
    })


# -----------------------------------------------------------------------------
# WORD (.DOCX) EXPORT
# -----------------------------------------------------------------------------
@login_required
def export_report_docx(request, report_id):
    """Download a saved report as a styled Microsoft Word (.docx) file."""
    report = get_object_or_404(AnalysisReport, id=report_id, user=request.user)
    doc_names = list(report.documents.values_list('title', flat=True))

    docx_buffer = create_docx_report(
        report_title=report.title,
        report_type_label=report.get_report_type_display(),
        document_names=doc_names,
        markdown_content=report.content,
        username=request.user.username,
    )

    clean_filename = "".join(c for c in report.title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    response = HttpResponse(
        docx_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="Paledoc_{clean_filename[:40]}.docx"'
    return response


# -----------------------------------------------------------------------------
# SYSTEM & SETTINGS VIEW
# -----------------------------------------------------------------------------
@login_required
def settings_view(request):
    from .services.vector_store import get_vector_store
    import os

    ollama_status = "Connected"
    ollama_error = None
    try:
        from .services.llm_service import get_llm
        llm = get_llm()
        test_resp = llm.invoke("Hi")
    except Exception as exc:
        ollama_status = "Disconnected / Error"
        ollama_error = str(exc)

    try:
        vs = get_vector_store()
        vector_count = vs._collection.count()
    except Exception:
        vector_count = "Unavailable"

    return render(request, 'documents/settings.html', {
        'ollama_status': ollama_status,
        'ollama_error': ollama_error,
        'vector_count': vector_count,
        'chroma_dir': settings.CHROMA_DATA_DIR,
        'llm_model': 'qwen3.5:4b (via ChatOllama)',
        'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',
        'reranker_model': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
    })
