import PyPDF2
import docx
import os
from werkzeug.utils import secure_filename

class ResumeParser:
    """Extract text from resume files (PDF and DOCX)"""
    
    def __init__(self):
        self.supported_formats = ['pdf', 'docx', 'doc']
    
    def extract_text(self, file_path):
        """
        Extract text from resume file
        
        Args:
            file_path: Path to resume file
            
        Returns:
            Extracted text as string
        """
        file_ext = file_path.rsplit('.', 1)[1].lower()
        
        if file_ext == 'pdf':
            return self._extract_from_pdf(file_path)
        elif file_ext in ['docx', 'doc']:
            return self._extract_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def _extract_from_pdf(self, file_path):
        """Extract text from PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()
            
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def _extract_from_docx(self, file_path):
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting text from DOCX: {str(e)}")
    
    def validate_file(self, filename):
        """Check if file has valid extension"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.supported_formats
