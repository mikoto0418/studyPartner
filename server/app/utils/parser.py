import hashlib
import io
import logging
from typing import List, Tuple

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

def _parse_docx_with_images(file_bytes: bytes) -> Tuple[str, List[dict]]:
    """一次遍历 docx 正文，按出现顺序同时产出文字与内嵌图片。"""
    import docx
    from docx.oxml.ns import qn

    document = docx.Document(io.BytesIO(file_bytes))
    part = document.part
    lines: List[str] = []
    images: List[dict] = []

    for paragraph in document.paragraphs:
        buffer: List[str] = []
        for run in paragraph.runs:
            for child in run._r:
                # 内联图片有两套标记：DrawingML 的 w:drawing 与老式 VML 的 w:pict
                if child.tag in (qn("w:drawing"), qn("w:pict")):
                    rel_id = None
                    for blip in child.iter(qn("a:blip")):
                        rel_id = blip.get(qn("r:embed"))
                        if rel_id:
                            break
                    if not rel_id:
                        for data_el in child.iter(qn("v:imagedata")):
                            rel_id = data_el.get(qn("r:id"))
                            if rel_id:
                                break
                    blob = None
                    if rel_id:
                        try:
                            blob = part.related_parts[rel_id].blob
                        except Exception:
                            blob = None
                    # 取不到就两边都不产出：宁可没标记，也不能让编号错位
                    if not blob:
                        continue
                    images.append({"data": blob, "ext": _guess_image_ext(blob) or "png"})
                    buffer.append(f"[[IMG:{len(images)}]]")
                elif child.tag == qn("w:t"):
                    buffer.append(child.text or "")
        lines.append("".join(buffer))
    return "\n".join(lines), images

def parse_document_with_images(file_bytes: bytes, filename: str) -> Tuple[str, List[dict]]:
    """一次遍历同时产出「带 [[IMG:n]] 占位符的文本」与「按同一编号排列的图片」。

    docx 必须成对产出：分成 parse_document + extract_images 两次调用时，文本侧拿不到
    图片位置，而图片侧是按 word/media/ 文件名排序（image1、image10、image2…），并不是
    文档顺序 —— 两边编号一旦错位，图就会挂到别的题上。编号从 1 开始，与占位符一一对应。
    """
    ext = (filename.split(".")[-1] or "").lower()
    if ext == "docx":
        try:
            return _parse_docx_with_images(file_bytes)
        except Exception as e:
            logger.error(f"Failed to parse docx with images {filename}: {e}", exc_info=True)
            raise ValueError(f"文档内容解析失败: {str(e)}")
    # pdf 的图片位置信息弱，暂时沿用旧的两段式（顺位可能不准，另行处理）
    return parse_document(file_bytes, filename), extract_images(file_bytes, filename)

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
