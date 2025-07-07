"""
Text Service - Text extraction, normalization, and structuring
"""
import re
from pathlib import Path
import PyPDF2
from utils.logging import get_logger
import subprocess
import tempfile
from PIL import Image
import pytesseract

logger = get_logger(__name__)

class TextService:
    def __init__(self, config):
        self.config = config

    def extract_and_structure_text(self, file_path: Path):
        """
        Main public method to extract, normalize, and structure text from a file.
        """
        raw_text = self._extract_raw_text(file_path)
        if not raw_text:
            return None

        normalized_text = self._normalize_text(raw_text)
        
        structured_text = self._structure_text(normalized_text)

        # For now, just return the structured text.
        # Later, this will save to a file.
        return structured_text

    def extract_full_text(self, file_path: Path, save_to_file: bool = True) -> dict:
        """
        Extract full text from a file, escalating from PyPDF2 to OCR.
        """
        result = {
            'success': False,
            'text': '',
            'text_length': 0,
            'method': 'none',
            'filename': None
        }
        
        try:
            logger.info(f"📄 Starting full text extraction from: {file_path.name}")
            
            # Try PyPDF2 first (fast for text-based PDFs)
            extracted_text = self._extract_text_with_pypdf2(file_path)
            
            if extracted_text and len(extracted_text.strip()) >= 100:
                result['text'] = extracted_text
                result['method'] = 'pypdf2'
                logger.info(f"✅ PyPDF2 extraction successful: {len(extracted_text)} characters")
            else:
                logger.info(f"⚠️ PyPDF2 extracted minimal text, trying OCR...")
                ocr_text = self._simple_ocr_extraction(file_path)
                
                if ocr_text and len(ocr_text.strip()) >= 50:
                    result['text'] = ocr_text
                    result['method'] = 'ocr'
                    logger.info(f"✅ OCR extraction successful: {len(ocr_text)} characters")
                else:
                    result['text'] = extracted_text if extracted_text else ''
                    result['method'] = 'failed'
                    logger.info(f"❌ Both PyPDF2 and OCR failed to extract meaningful text")
                    return result
            
            result['text_length'] = len(result['text'])
            result['success'] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"💥 Full text extraction failed: {e}")
            result['error'] = str(e)
            return result

    def _extract_text_with_pypdf2(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyPDF2 (fast, no OCR required)"""
        try:
            with open(pdf_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                all_text = [page.extract_text() for page in pdf.pages if page.extract_text()]
                return '\n\n'.join(all_text)
        except Exception as e:
            logger.error(f"❌ PyPDF2 extraction failed for {pdf_path.name}: {e}")
            return ""

    def _simple_ocr_extraction(self, pdf_path: Path) -> str:
        """Simple OCR extraction that converts entire PDF to images and processes them"""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                cmd = ['pdftoppm', '-png', '-r', '200', str(pdf_path), str(tmp_path / "page")]
                subprocess.run(cmd, capture_output=True, timeout=300)
                
                png_files = sorted(list(tmp_path.glob("*.png")))
                if not png_files: return ""
                
                all_text = []
                for i, png_file in enumerate(png_files[:10]): # Limit to first 10 pages
                    try:
                        with Image.open(png_file) as img:
                            text = pytesseract.image_to_string(img, lang='eng')
                            if text.strip():
                                all_text.append(f"--- Page {i+1} ---\n{text}")
                    except Exception as e:
                        logger.warning(f"    ❌ Error processing {png_file.name}: {e}")
                        continue
                return '\n\n'.join(all_text)
        except Exception as e:
            logger.error(f"💥 Simple OCR extraction failed for {pdf_path.name}: {e}")
            return ""

    def _normalize_text(self, raw_text: str) -> str:
        """Cleans and normalizes raw extracted text."""
        logger.info("Normalizing extracted text...")
        # ... (implementation for normalization) ...
        # 1. Fix line breaks and hyphenation
        # 2. Remove headers/footers
        # 3. Standardize encoding/ligatures
        # 4. Strip page numbers
        return "Normalized text placeholder"

    def _structure_text(self, normalized_text: str) -> dict:
        """Structures normalized text into a paginated JSON format."""
        logger.info("Structuring text...")
        # ... (implementation for structuring) ...
        # 1. Create metadata header
        # 2. Paginate text into paragraphs with position data
        return {"metadata": {}, "pages": []} 