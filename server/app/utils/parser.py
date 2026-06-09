import io
import logging
from typing import List

logger = logging.getLogger(__name__)

def parse_document(file_bytes: bytes, filename: str) -> str:
    """Parses document file content to raw plain text based on file extension"""
    ext = filename.split(".")[-1].lower()
    
    try:
        if ext == "pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
            return text
            
        elif ext in ["docx", "doc"]:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
            
        elif ext in ["txt", "md", "markdown", "json", "html"]:
            return file_bytes.decode("utf-8", errors="ignore")
            
        else:
            # Plain text representation for unhandled formats
            return file_bytes.decode("utf-8", errors="ignore")
            
    except Exception as e:
        logger.error(f"Failed to parse document {filename}: {e}", exc_info=True)
        raise ValueError(f"文档内容解析失败: {str(e)}")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Slices plain text into chunks with a sliding window overlap"""
    # Clean text to remove empty lines and standardize whitespace
    cleaned_text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
    
    chunks = []
    if not cleaned_text:
        return chunks
        
    start = 0
    while start < len(cleaned_text):
        end = start + chunk_size
        chunks.append(cleaned_text[start:end])
        # Move window forward by chunk_size - overlap
        start += chunk_size - overlap
        
    return chunks
