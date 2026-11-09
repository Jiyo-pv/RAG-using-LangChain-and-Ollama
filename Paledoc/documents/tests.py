import io
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from documents.models import AnalysisReport, Conversation, Document, Message
from documents.forms import DocumentForm
from documents.services.hybrid_retrieval import _rrf_fuse
from documents.services.rag_service import ask_paledoc
from langchain_core.documents import Document as LCDocument

User = get_user_model()


class AuthenticationTests(TestCase):
    """Test user registration, login, logout, and access control."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='alice',
            password='Password123!',
        )

    def test_registration_success(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'bob',
            'password1': 'Password123!',
            'password2': 'Password123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='bob').exists())

    def test_registration_password_mismatch(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'charlie',
            'password1': 'Password123!',
            'password2': 'DifferentPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='charlie').exists())

    def test_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'alice',
            'password': 'Password123!',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'alice',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_login_required_protection(self):
        protected_urls = [
            reverse('dashboard'),
            reverse('document_list'),
            reverse('upload'),
            reverse('chat_index'),
            reverse('summarization'),
            reverse('comparison'),
            reverse('research_analysis'),
            reverse('reference_generator'),
            reverse('settings'),
        ]
        for url in protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/accounts/login/', resp.url)


class PDFValidationTests(TestCase):
    """Test file validation: extensions, magic bytes, and size limits."""

    def test_valid_pdf_form_acceptance(self):
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        upload = SimpleUploadedFile("test.pdf", pdf_content, content_type="application/pdf")
        form = DocumentForm(data={'title': 'Test Document'}, files={'file': upload})
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_extension_rejected(self):
        fake_content = b"%PDF-1.4 hello"
        upload = SimpleUploadedFile("test.exe", fake_content, content_type="application/octet-stream")
        form = DocumentForm(data={'title': 'Test Exe'}, files={'file': upload})
        self.assertFalse(form.is_valid())
        self.assertIn("Only PDF files are allowed", str(form.errors))

    def test_fake_pdf_magic_bytes_rejected(self):
        txt_content = b"This is just a text file renamed to pdf."
        upload = SimpleUploadedFile("fake.pdf", txt_content, content_type="application/pdf")
        form = DocumentForm(data={'title': 'Fake PDF'}, files={'file': upload})
        self.assertFalse(form.is_valid())
        self.assertIn("not a valid PDF", str(form.errors))


class UserIsolationTests(TestCase):
    """Ensure strict server-side multi-tenant isolation."""

    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', password='Password123!')
        self.user_b = User.objects.create_user(username='userb', password='Password123!')

        self.doc_a = Document.objects.create(
            user=self.user_a,
            title="User A Secret Doc",
            original_filename="secret_a.pdf",
            status="completed",
        )
        self.doc_b = Document.objects.create(
            user=self.user_b,
            title="User B Secret Doc",
            original_filename="secret_b.pdf",
            status="completed",
        )

        self.conv_b = Conversation.objects.create(
            user=self.user_b,
            title="User B Private Chat",
        )
        self.report_b = AnalysisReport.objects.create(
            user=self.user_b,
            title="User B Report",
            report_type="summary_short",
            content="Confidential report",
        )

    def test_user_a_cannot_see_user_b_document_in_list(self):
        self.client.login(username='usera', password='Password123!')
        response = self.client.get(reverse('document_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User A Secret Doc")
        self.assertNotContains(response, "User B Secret Doc")

    def test_user_a_cannot_view_user_b_document_detail(self):
        self.client.login(username='usera', password='Password123!')
        response = self.client.get(reverse('document_detail', args=[self.doc_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_a_cannot_delete_user_b_document(self):
        self.client.login(username='usera', password='Password123!')
        response = self.client.post(reverse('delete_document', args=[self.doc_b.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(pk=self.doc_b.pk).exists())

    def test_user_a_cannot_access_user_b_conversation(self):
        self.client.login(username='usera', password='Password123!')
        response = self.client.get(reverse('chat_conversation', args=[self.conv_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_a_cannot_export_user_b_report(self):
        self.client.login(username='usera', password='Password123!')
        response = self.client.get(reverse('export_report_docx', args=[self.report_b.pk]))
        self.assertEqual(response.status_code, 404)


class HybridRetrievalAndFusionTests(TestCase):
    """Test Reciprocal Rank Fusion and hybrid retrieval logic."""

    def test_rrf_fusion_deduplication_and_ranking(self):
        doc1 = LCDocument(page_content="Machine learning fundamentals", metadata={"page": 1})
        doc2 = LCDocument(page_content="Neural networks and deep learning", metadata={"page": 2})
        doc3 = LCDocument(page_content="Support vector machines", metadata={"page": 3})

        list_a = [doc1, doc2]
        list_b = [doc2, doc3]

        fused = _rrf_fuse([list_a, list_b])
        self.assertEqual(len(fused), 3)
        self.assertEqual(fused[0].page_content, "Neural networks and deep learning")


class ChatAndMissingInformationTests(TestCase):
    """Test AI chat response behavior and missing-information compliance."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='Password123!')

    @patch('documents.services.rag_service.RAG_PROMPT')
    @patch('documents.services.rag_service.get_llm')
    @patch('documents.services.rag_service.hybrid_retrieve')
    def test_missing_information_when_no_chunks_found(self, mock_retrieve, mock_llm, mock_prompt):
        mock_retrieve.return_value = []
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content="The information is not available in the selected documents.")
        mock_prompt.__or__.return_value = mock_chain

        answer, sources = ask_paledoc(
            question="What is the quantum speedup?",
            user_id=self.user.id,
            doc_ids=None,
        )
        self.assertIn("not available in the selected documents", answer)
        self.assertEqual(len(sources), 0)

    def test_conversation_and_message_persistence(self):
        conv = Conversation.objects.create(user=self.user, title="Test Session")
        user_msg = Message.objects.create(
            conversation=conv,
            role='user',
            content="Hello Paledoc",
        )
        asst_msg = Message.objects.create(
            conversation=conv,
            role='assistant',
            content="Hello! How can I help you?",
            sources=[{"filename": "test.pdf", "page": 1, "excerpt": "sample text"}],
        )

        self.assertEqual(conv.messages.count(), 2)
        self.assertEqual(asst_msg.sources[0]["page"], 1)
        self.assertEqual(asst_msg.sources[0]["filename"], "test.pdf")
