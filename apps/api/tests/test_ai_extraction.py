from io import BytesIO
import zipfile, json
import pytest, httpx
from app.ai.extraction import extract, extract_isolated, ExtractionError
from app.ai.embeddings import Embeddings
from app.ai.providers.base import ProviderUnavailable


def docx(xml):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return stream.getvalue()


def test_txt_docx_chunks_and_sanitisation():
    chunks = extract(
        b"Contact owner@example.com password=secret\x00. " + b"check radio " * 200,
        "txt",
    )
    assert len(chunks) > 1 and len(chunks[0][1]) <= 1400
    assert "owner@example.com" not in str(chunks) and "\x00" not in str(chunks)
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Emergency procedure</w:t></w:r></w:p></w:body></w:document>'
    assert extract(docx(xml), "docx") == [("Document", "Emergency procedure")]
    assert extract_isolated(b"Check radio", "txt") == [("Text", "Check radio")]


@pytest.mark.parametrize(
    "data,kind",
    [
        (b"", "txt"),
        (b"\xff", "txt"),
        (b"x" * 120001, "txt"),
        (b"not pdf", "pdf"),
        (b"not docx", "docx"),
        (
            docx('<!DOCTYPE a [<!ENTITY e SYSTEM "file:///etc/passwd">]><a>&e;</a>'),
            "docx",
        ),
    ],
)
def test_invalid_and_hostile_files_are_rejected(data, kind):
    with pytest.raises(ExtractionError):
        extract(data, kind)


def test_pdf_without_text_needs_ocr():
    from pypdf import PdfWriter

    out = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(out)
    with pytest.raises(ExtractionError, match="no_text"):
        extract(out.getvalue(), "pdf")


def test_real_embedding_wire_contract_and_shape_validation(monkeypatch):
    from app.config import settings

    for key, value in {
        "ai_knowledge_enabled": True,
        "ai_embedding_base_url": "https://embeddings.invalid",
        "ai_embedding_api_key": "server-secret",
        "ai_embedding_model": "model-384",
        "ai_embedding_version": "v1",
        "app_env": "production",
    }.items():
        monkeypatch.setattr(settings, key, value)
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.path == "/v1/embeddings"
        assert json.loads(request.content) == {
            "model": "model-384",
            "input": ["Check radio"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [1.0] + [0.0] * 383}]}
        )

    assert (
        len(Embeddings(httpx.MockTransport(handler)).embed(["Check radio"])[0]) == 384
    )
    assert seen[0].headers["authorization"] == "Bearer server-secret"
    for value in [[], [0.0] * 384, [float("nan")] * 384, [True] * 384]:
        # JSON cannot encode NaN in httpx; transport may return raw malformed data.
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=json.dumps({"data": [{"index": 0, "embedding": value}]})
            )
        )
        with pytest.raises(ProviderUnavailable):
            Embeddings(transport).embed(["Check radio"])


def test_text_pdf_extracts_actual_page_provenance():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 200 Td (Check the emergency radio.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    assert extract(stream.getvalue(), "pdf") == [
        ("Page 1", "Check the emergency radio.")
    ]
