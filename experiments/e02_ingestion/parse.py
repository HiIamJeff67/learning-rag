from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from statistics import median
import re
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from markdown_it import MarkdownIt
import pdfplumber


SUFFIXES = {".rst", ".txt", ".md", ".html", ".htm", ".pdf"}
_HEADING = re.compile(r"([=\-~`^\"#*+_:.])\1{2,}")
_PARAGRAPH_END = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")
_INLINE = {"a", "abbr", "b", "code", "em", "i", "kbd", "mark", "span", "strong", "sub", "sup", "u"}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str
    section: str = ""
    page: int | None = None


@dataclass(frozen=True)
class Document:
    text: str
    spans: tuple[Span, ...]


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_document(data: bytes, suffix: str) -> Document:
    if suffix == ".pdf":
        blocks = _pdf_blocks(data)
    else:
        text = normalize(data.decode("utf-8-sig"))
        if suffix == ".md":
            html = MarkdownIt("commonmark", {"html": False}).enable("table").render(text)
            blocks = _html_blocks(html)
        elif suffix in {".html", ".htm"}:
            blocks = _html_blocks(text)
        elif suffix in {".rst", ".txt"}:
            return Document(text, tuple(_plain_spans(text, rst=suffix == ".rst")))
        else:
            raise ValueError(f"unsupported document type: {suffix}")

    parts: list[str] = []
    spans: list[Span] = []
    offset = 0
    for kind, content, section, page in blocks:
        if not content.strip():
            continue
        part = normalize(content) + "\n\n"
        parts.append(part)
        spans.append(Span(offset, offset + len(part), kind, section, page))
        offset += len(part)
    return Document("".join(parts), tuple(spans))


def _plain_spans(text: str, *, rst: bool) -> Iterator[Span]:
    sections = [(0, "")]
    if rst:
        lines = text.splitlines(keepends=True)
        levels: dict[str, int] = {}
        headings: list[str] = []
        offset = 0
        for line, underline in zip(lines, lines[1:]):
            title = line.rstrip()
            rule = underline.rstrip()
            if (
                title and not title[0].isspace()
                and _HEADING.fullmatch(rule) and len(rule) >= len(title)
            ):
                level = levels.setdefault(rule[0], len(levels))
                headings[level:] = [title]
                label = " > ".join(headings)
                if offset == 0:
                    sections[0] = (0, label)
                else:
                    sections.append((offset, label))
            offset += len(line)

    ends = [offset for offset, _ in sections[1:]] + [len(text)]
    for (start, section), end in zip(sections, ends):
        for boundary in _PARAGRAPH_END.finditer(text, start, end):
            kind = "code" if text[start:start + 1] in {" ", "\t"} else "paragraph"
            yield Span(start, boundary.end(), kind, section)
            start = boundary.end()
        if start < end:
            kind = "code" if text[start:start + 1] in {" ", "\t"} else "paragraph"
            yield Span(start, end, kind, section)


def _table_rows(rows: list[list[str]], header_count: int) -> Iterator[str]:
    width = max((len(row) for row in rows), default=0)
    headers: list[str] = []
    for column in range(width):
        labels = [row[column] for row in rows[:header_count] if len(row) > column and row[column]]
        headers.append(" / ".join(dict.fromkeys(labels)) or f"Column {column + 1}")
    for row in rows[header_count:]:
        if any(row):
            yield "\n".join(f"{headers[i]}: {value}" for i, value in enumerate(row))
    if rows and header_count == len(rows):
        yield "\n".join(headers)


def _html_rows(table: Tag) -> tuple[list[list[str]], int]:
    lines = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    grid: dict[tuple[int, int], str] = {}
    header_count = 0
    width = 0
    for i, row in enumerate(lines):
        cells = row.find_all(["th", "td"], recursive=False)
        if i == header_count and cells and (
            all(cell.name == "th" for cell in cells) or row.find_parent("thead") is not None
        ):
            header_count += 1
        col = 0
        for cell in cells:
            while (i, col) in grid:
                col += 1
            text = " ".join(cell.get_text().split())
            row_count = str(cell.get("rowspan", "1"))
            col_count = str(cell.get("colspan", "1"))
            down = int(row_count) if row_count.isdecimal() and len(row_count) < 6 else 1
            across = int(col_count) if col_count.isdecimal() and len(col_count) < 6 else 1
            down = min(down or len(lines) - i, len(lines) - i)
            across = min(max(1, across), 1000)
            for y in range(i, i + down):
                for x in range(col, col + across):
                    grid.setdefault((y, x), text)
            col += across
            width = max(width, col)
    return [[grid.get((i, col), "") for col in range(width)] for i in range(len(lines))], header_count


def _html_blocks(html: str) -> Iterator[tuple[str, str, str, int | None]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "template", "head"]):
        tag.decompose()
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    headings: list[tuple[int, str]] = []

    def visit(node: Tag) -> Iterator[tuple[str, str, str, int | None]]:
        prose: list[str] = []
        for child in node.children:
            section = " > ".join(title for _, title in headings)
            if isinstance(child, NavigableString) and not isinstance(child, Comment):
                prose.append(str(child))
            elif isinstance(child, Tag):
                name = child.name
                if name in _INLINE:
                    prose.append(child.get_text())
                    continue
                text = " ".join("".join(prose).split())
                if text:
                    yield "paragraph", text, section, None
                prose.clear()
                if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    level = int(name[1])
                    title = " ".join(child.get_text().split())
                    while headings and headings[-1][0] >= level:
                        headings.pop()
                    headings.append((level, title))
                    yield "heading", title, " > ".join(title for _, title in headings), None
                elif name == "table":
                    caption = child.find("caption", recursive=False)
                    if caption:
                        label = " ".join(caption.get_text().split())
                        section = " > ".join(filter(None, [section, label]))
                        yield "heading", label, section, None
                    rows, header_count = _html_rows(child)
                    for row in _table_rows(rows, header_count):
                        yield "table-row", row, section, None
                elif name == "pre":
                    yield "code", child.get_text().strip("\n"), section, None
                elif name in {"p", "dt", "dd"}:
                    yield "paragraph", " ".join(child.get_text().split()), section, None
                else:
                    yield from visit(child)
        text = " ".join("".join(prose).split())
        if text:
            yield "paragraph", text, " > ".join(title for _, title in headings), None

    yield from visit(soup.body or soup)


def _pdf_blocks(data: bytes) -> Iterator[tuple[str, str, str, int]]:
    section = ""
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            page_number = page.page_number
            page = page.dedupe_chars()
            tables = page.find_tables()
            boxes = [table.bbox for table in tables]
            # Table text is emitted once, from its cells rather than its drawing order.
            def outside_tables(obj: dict[str, Any]) -> bool:
                if obj["object_type"] != "char":
                    return True
                x = (float(obj["x0"]) + float(obj["x1"])) / 2
                y = (float(obj["top"]) + float(obj["bottom"])) / 2
                return not any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in boxes)

            lines = page.filter(outside_tables).extract_text_lines()
            body_sizes = [float(char["size"]) for line in lines for char in line["chars"]]
            body_size = median(body_sizes) if body_sizes else 0.0
            items = [(line["top"], "line", line) for line in lines]
            items.extend((table.bbox[1], "table", table.extract()) for table in tables)
            paragraph: list[str] = []
            code: list[tuple[float, str]] = []
            title_lines: list[str] = []
            title_size = 0.0
            cell_width = 1.0
            last_bottom: float | None = None
            for top, kind, value in sorted(items, key=lambda item: item[0]):
                chars = [] if kind == "table" else [char for char in value["chars"] if char["text"].strip()]
                if kind == "line" and not chars:
                    continue
                is_code = bool(chars) and all(
                    any(word in char["fontname"].lower() for word in ("mono", "courier"))
                    for char in chars
                )
                size = median(float(char["size"]) for char in chars) if chars else 0.0
                heading = bool(chars) and not is_code and size >= 1.2 * body_size
                separated = last_bottom is not None and top - last_bottom > max(4, body_size * 0.65)
                if title_lines and (not heading or separated or abs(size - title_size) > 0.5):
                    section = " ".join(title_lines)
                    yield "heading", section, section, page_number
                    title_lines.clear()
                if paragraph and (kind == "table" or is_code or heading or separated):
                    yield "paragraph", " ".join(paragraph), section, page_number
                    paragraph.clear()
                if code and (not is_code or separated):
                    origin = min(x for x, _ in code)
                    content = "\n".join(" " * round((x - origin) / cell_width) + line for x, line in code)
                    yield "code", content, section, page_number
                    code.clear()
                if kind == "table":
                    rows = [[" ".join((cell or "").split()) for cell in row] for row in value]
                    header_count = int(len(rows) > 1 and all(rows[0]) and len(set(rows[0])) == len(rows[0]))
                    for row in _table_rows(rows, header_count):
                        yield "table-row", row, section, page_number
                    last_bottom = None
                else:
                    line = value["text"].strip()
                    last_bottom = value["bottom"]
                    if is_code:
                        if not code:
                            cell_width = max(0.1, float(chars[0]["x1"]) - float(chars[0]["x0"]))
                        code.append((min(float(char["x0"]) for char in chars), line))
                    elif heading:
                        title_size = size
                        title_lines.append(line)
                    else:
                        paragraph.append(line)
            if paragraph:
                yield "paragraph", " ".join(paragraph), section, page_number
            if code:
                origin = min(x for x, _ in code)
                content = "\n".join(" " * round((x - origin) / cell_width) + line for x, line in code)
                yield "code", content, section, page_number
            if title_lines:
                section = " ".join(title_lines)
                yield "heading", section, section, page_number
