from django import forms
from django.conf import settings

from .models import Document


class DocumentForm(forms.ModelForm):

    class Meta:
        model = Document
        fields = ['title', 'file']

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')

        if not uploaded_file:
            return uploaded_file

        # Validate file extension
        name = uploaded_file.name.lower()
        if not name.endswith('.pdf'):
            raise forms.ValidationError("Only PDF files are allowed.")

        # Validate magic bytes (%PDF)
        uploaded_file.seek(0)
        header = uploaded_file.read(4)
        uploaded_file.seek(0)

        if header != b'%PDF':
            raise forms.ValidationError("The uploaded file is not a valid PDF.")

        # Validate file size
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 50 * 1024 * 1024)
        if uploaded_file.size > max_size:
            max_mb = max_size // (1024 * 1024)
            raise forms.ValidationError(
                f"File size exceeds the maximum allowed size of {max_mb} MB."
            )

        return uploaded_file
