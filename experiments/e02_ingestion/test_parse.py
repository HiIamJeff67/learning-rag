from io import BytesIO

import pytest
from reportlab.pdfgen.canvas import Canvas

from .chunk import ChunkSpec, chunk_document
from .parse import parse_document


@pytest.fixture
def policy_pdf() -> bytes:
    output = BytesIO()
    page = Canvas(output, pagesize=(360, 480), invariant=1)
    page.setFont("Helvetica-Bold", 18)
    page.drawString(36, 452, "Return")
    page.drawString(36, 431, "policy")
    page.setFont("Helvetica", 10)
    page.drawString(36, 405, "Refunds apply to items returned")
    page.drawString(36, 392, "within 14 days.")
    for y in (380, 360, 340, 320):
        page.line(36, y, 316, y)
    for x in (36, 166, 316):
        page.line(x, 320, x, 380)
    for y, row in zip((366, 346, 326), [
        ("Category", "Window"), ("Regular", "14 days"), ("Sale", "No returns"),
    ]):
        page.drawString(42, y, row[0])
        page.drawString(172, y, row[1])
    page.showPage()
    page.setFont("Helvetica-Bold", 18)
    page.drawString(36, 444, "Approval example")
    page.setFont("Courier", 10)
    page.drawString(36, 417, "if can_refund:")
    page.drawString(60, 404, "approve()")
    page.save()
    return output.getvalue()


def test_pdf_joins_visual_wrap_inside_paragraph(policy_pdf):
    document = parse_document(policy_pdf, ".pdf")
    assert "Refunds apply to items returned within 14 days." in document.text
    headings = [span.section for span in document.spans if span.kind == "heading" and span.page == 1]
    assert headings == ["Return policy"]


def test_pdf_table_keeps_each_value_with_its_header(policy_pdf):
    document = parse_document(policy_pdf, ".pdf")
    rows = [document.text[span.start:span.end].strip()
            for span in document.spans if span.kind == "table-row"]
    assert rows == ["Category: Regular\nWindow: 14 days", "Category: Sale\nWindow: No returns"]
    assert document.text.count("No returns") == 1


def test_pdf_keeps_code_indentation_and_page_number(policy_pdf):
    document = parse_document(policy_pdf, ".pdf")
    [span] = [span for span in document.spans if span.kind == "code"]
    assert document.text[span.start:span.end].rstrip("\n") == "if can_refund:\n    approve()"
    assert span.section == "Approval example" and span.page == 2
    for strategy in ("fixed", "recursive", "section"):
        for chunk in chunk_document(document, ChunkSpec(strategy)):
            assert chunk.page == (2 if "approve()" in chunk.text else 1)


def test_markdown_fence_keeps_indentation_and_blank_lines():
    data = (
        b"## Approval\r\n\r\n"
        b"```python\r\nif can_refund:\r\n    approve()\r\n\r\nnotify()\r\n```\r\n"
    )
    document = parse_document(data, ".md")
    [code] = [span for span in document.spans if span.kind == "code"]
    assert code.section == "Approval"
    assert document.text[code.start:code.end] == "if can_refund:\n    approve()\n\nnotify()\n\n"


def test_markdown_table_keeps_escaped_pipe_and_row_labels():
    document = parse_document(
        b"# Operators\n\n| Name | Example |\n|---|---|\n| Union | a \\| b |\n", ".md",
    )
    assert "Name: Union\nExample: a | b" in document.text


def test_html_spanned_cells_remain_associated_with_headers():
    document = parse_document(b"""
      <h1>Delivery</h1><table>
      <thead><tr><th rowspan="2">Region</th><th colspan="2">Standard</th></tr>
      <tr><th>Fee</th><th>Days</th></tr></thead>
      <tr><td rowspan="2">Taipei</td><td>100</td><td>2</td></tr>
      <tr><td>150</td><td>1</td></tr></table>
      <script>ignore this</script>
    """, ".html")
    assert "Region: Taipei\nStandard / Fee: 100\nStandard / Days: 2" in document.text
    assert "Region: Taipei\nStandard / Fee: 150\nStandard / Days: 1" in document.text
    assert "ignore this" not in document.text


def test_html_keeps_inline_text_in_its_list_item():
    document = parse_document(b"<ul><li>Use <code>refund()</code> within 14 days.</li></ul>", ".html")
    assert document.text == "Use refund() within 14 days.\n\n"
    assert len(document.spans) == 1


def test_section_strategy_keeps_adjacent_rules_separate():
    document = parse_document(
        b"Regular items\n=============\n\nRefund within 14 days.\n\n"
        b"Sale items\n==========\n\nNo refunds.\n",
        ".rst",
    )
    [fixed] = chunk_document(document, ChunkSpec("fixed"))
    regular, sale = chunk_document(document, ChunkSpec("section"))
    assert "Refund within" in fixed.text and "No refunds" in fixed.text
    assert regular.section == "Regular items" and "No refunds" not in regular.text
    assert sale.section == "Sale items" and "Refund within" not in sale.text


def test_recursive_chunks_cover_long_words_and_keep_whole_word_overlap():
    document = parse_document(b"alpha beta gamma delta epsilon zeta theta iota", ".txt")
    chunks = chunk_document(document, ChunkSpec("recursive", 18, 6))
    assert all(len(chunk.text) <= 18 for chunk in chunks)
    end = 0
    for chunk in chunks:
        assert 0 <= end - chunk.start <= 6
        assert chunk.start == 0 or document.text[chunk.start - 1] == " "
        end = chunk.start + len(chunk.text)
    assert end == len(document.text)
    word = parse_document(b"abcdefghijklmnopqrstuvwxyz", ".txt")
    assert "".join(chunk.text for chunk in chunk_document(word, ChunkSpec("recursive", 8, 0))) == word.text
