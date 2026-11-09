from django.conf import settings
from django.db import models


class Document(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )
    page_count = models.IntegerField(default=0)
    file_size = models.BigIntegerField(default=0)
    original_filename = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.title


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    title = models.CharField(max_length=255, default='New Conversation')
    documents = models.ManyToManyField(
        Document,
        blank=True,
        related_name='conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role.capitalize()}: {self.content[:40]}..."


class AnalysisReport(models.Model):
    REPORT_TYPES = [
        ('summary_short', 'Short Summary'),
        ('summary_detailed', 'Detailed Summary'),
        ('summary_sections', 'Section-wise Summary'),
        ('summary_findings', 'Key Findings & Concepts'),
        ('research_analysis', 'Research Paper Analysis'),
        ('comparison', 'Multi-Document Comparison'),
        ('citation_apa', 'APA Reference'),
        ('citation_ieee', 'IEEE Reference'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    title = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    documents = models.ManyToManyField(Document, related_name='reports')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.title}"
