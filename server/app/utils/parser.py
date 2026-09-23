import hashlib
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


def _guess_image_ext(data: bytes) -> str:
    """Guesses image file extension from magic bytes."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return ""


def extract_images(file_bytes: bytes, filename: str) -> List[dict]:
    """Extracts embedded images from PDF/docx files in document order.

    Returns a list of dicts: [{"data": bytes, "ext": "png"}, ...]
    """
    ext = filename.split(".")[-1].lower()
    images: List[dict] = []

    if ext == "pdf":
        import pypdf

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            seen = set()
            for page in reader.pages:
                try:
                    page_images = page.images or []
                except Exception:
                    continue
                for img in page_images:
                    if img is None:
                        continue
                    try:
                        data = getattr(img, "data", None)
                    except Exception:
                        data = None
                    if not data:
                        continue
                    fmt = _guess_image_ext(data)
                    if not fmt:
                        continue
                    digest = hashlib.sha256(data).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)
                    images.append({"data": data, "ext": fmt})
        except Exception as e:
            logger.warning(f"PDF image extraction failed: {e}")

    elif ext in ["docx", "doc"]:
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                names = sorted(n for n in z.namelist() if n.startswith("word/media/"))
                for n in names:
                    try:
                        data = z.read(n)
                        fmt = n.rsplit(".", 1)[-1].lower()
                        if fmt not in {"png", "jpg", "jpeg", "gif", "webp", "bmp"}:
                            fmt = _guess_image_ext(data) or "png"
                        images.append({"data": data, "ext": fmt})
                    except Exception as e:
                        logger.warning(f"DOCX image extract skipped {n}: {e}")
        except Exception as e:
            logger.warning(f"DOCX image extraction failed: {e}")

    return images
