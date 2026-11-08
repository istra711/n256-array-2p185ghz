"""A minimal, dependency-free OpenDocument Text writer.

Why not python-docx + LibreOffice
---------------------------------
The report has to be rebuildable from the repository with no extra installs, and
the layout has to be exact (A4, 16.6 cm text column, figures sized to it).  ODF is
a zip of XML documents; writing it directly keeps the build a single script and
makes the source of every style visible.

What is supported
-----------------
Paragraph styles, character styles, an outline-numbered table of contents with
live links, tables with shaded header rows and repeating headers, embedded PNG
figures with captions, code blocks, callout boxes, page breaks, headers and
footers with a page number, and a cover page with its own master page.

Everything else ODF offers is deliberately absent.
"""

from __future__ import annotations

import os
import re
import zipfile
from xml.sax.saxutils import escape

from PIL import Image

TEXT_WIDTH_CM = 16.6

MIMETYPE = "application/vnd.oasis.opendocument.text"

NS = """xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2"
 xmlns:loext="urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0\""""

INLINE = re.compile(r"(\*\*.+?\*\*|`.+?`|\*[^*]+?\*|_.+?_)", re.S)


def _inline(text: str) -> str:
    """Escape and apply the tiny inline markup: **bold**, `code`, *italic*, _sub_."""
    out = []
    for chunk in INLINE.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**") and len(chunk) > 4:
            out.append(f'<text:span text:style-name="Bold">{_inline(chunk[2:-2])}</text:span>')
        elif chunk.startswith("`") and chunk.endswith("`") and len(chunk) > 2:
            out.append(f'<text:span text:style-name="Code">{escape(chunk[1:-1])}</text:span>')
        elif chunk.startswith("*") and chunk.endswith("*") and len(chunk) > 2:
            out.append(f'<text:span text:style-name="Italic">{_inline(chunk[1:-1])}</text:span>')
        else:
            out.append(escape(chunk))
    return "".join(out)


def _plain(text: str) -> str:
    """Escape, dropping the inline markup markers (for table headers, which are styled)."""
    return escape(text.replace("**", "").replace("`", ""))


class Report:
    def __init__(self, title: str, author: str, subject: str,
                 header: str = "2.5D planar MoM for multilayer PCBs — implementation report",
                 toc_title: str = "Contents"):
        self.title = title
        self.author = author
        self.subject = subject
        self.header = header
        self.toc_title = toc_title
        self.body: list[str] = []
        self.auto: list[str] = []
        self.headings: list[tuple[int, str, str, str]] = []   # level, number, title, anchor
        self.pages: dict[str, int] = {}                        # TOC label -> page number
        self.fig_n = 0
        self.tab_n = 0
        #: caption prefixes (override for other languages)
        self.figure_word = "Figure"
        self.table_word = "Table"
        self._anchor = 0

    # ---------------------------------------------------------------- text
    def _p(self, style: str, text: str, extra: str = "") -> str:
        return f'<text:p text:style-name="{style}"{extra}>{_inline(text)}</text:p>'

    def p(self, text: str, style: str = "Body") -> None:
        self.body.append(self._p(style, text))

    def lead(self, text: str) -> None:
        self.body.append(self._p("Lead", text))

    def h1(self, number: str, title: str) -> None:
        self._heading(1, number, title, "H1")

    def h2(self, number: str, title: str) -> None:
        self._heading(2, number, title, "H2")

    def h3(self, number: str, title: str) -> None:
        self._heading(3, number, title, "H3")

    def _heading(self, level: int, number: str, title: str, style: str) -> None:
        self._anchor += 1
        anchor = f"sec{self._anchor}"
        self.headings.append((level, number, title, anchor))
        label = f"{number}  {title}" if number else title
        self.body.append(
            f'<text:h text:style-name="{style}" text:outline-level="{level}">'
            f'<text:bookmark text:name="{anchor}"/>{_inline(label)}</text:h>')

    def bullets(self, items: list[str]) -> None:
        for item in items:
            self.body.append(
                f'<text:p text:style-name="Bullet">•\u00a0\u00a0{_inline(item)}</text:p>')

    def numbered(self, items: list[str]) -> None:
        for i, item in enumerate(items, 1):
            self.body.append(
                f'<text:p text:style-name="Numbered">{i}.\u00a0\u00a0{_inline(item)}</text:p>')

    def _section(self, kind: str, inner: list[str]) -> None:
        self._sec_n = getattr(self, "_sec_n", 0) + 1
        self.body.append(
            f'<text:section text:name="{kind}{self._sec_n}" text:style-name="{kind}">'
            + "".join(inner) + "</text:section>")

    def code(self, block: str) -> None:
        lines = block.rstrip("\n").split("\n")
        inner = "<text:line-break/>".join(escape(line) or " " for line in lines)
        self.body.append(f'<text:p text:style-name="CodeBlock">{inner}</text:p>')

    def note(self, title: str, text: str) -> None:
        self._section("NoteSection", [self._p("NoteTitle", title), self._p("Note", text)])

    def start_main(self) -> None:
        """Start the numbered body on a Standard (headered) page after the cover."""
        self.body.append('<text:p text:style-name="AfterCover"/>')

    def page_break(self) -> None:
        self.body.append('<text:p text:style-name="Break"/>')

    def toc(self) -> None:
        """Place the (auto-generated) table of contents here."""
        self.body.append("<!--TOC-->")

    # -------------------------------------------------------------- figures
    def figure(self, path: str, caption: str, width_cm: float = TEXT_WIDTH_CM) -> None:
        self.fig_n += 1
        with Image.open(path) as im:
            w, h = im.size
        height_cm = width_cm * h / w
        name = f"fig{self.fig_n:02d}"
        self._pictures = getattr(self, "_pictures", [])
        self._pictures.append((path, f"Pictures/{name}.png"))
        self.body.append(
            f'<text:p text:style-name="Figure">'
            f'<draw:frame draw:name="{name}" '
            f'text:anchor-type="as-char" svg:width="{width_cm:.2f}cm" '
            f'svg:height="{height_cm:.2f}cm">'
            f'<draw:image xlink:href="Pictures/{name}.png" xlink:type="simple" '
            f'xlink:show="embed" xlink:actuate="onLoad"/>'
            f'</draw:frame></text:p>')
        self.body.append(self._p(
            "Caption", f"**{self.figure_word} {self.fig_n}.**  {caption}"))

    # --------------------------------------------------------------- tables
    def table(self, caption: str, headers: list[str], rows: list[list[str]],
              widths: list[float], source: str = "", align: str = "left") -> None:
        self.tab_n += 1
        name = f"T{self.tab_n}"
        scale = TEXT_WIDTH_CM / sum(widths)
        cols = []
        for i, w in enumerate(widths):
            wc = w * scale
            st = f"{name}c{i}"
            self.auto.append(
                f'<style:style style:name="{st}" style:family="table-column">'
                f'<style:table-column-properties style:column-width="{wc:.3f}cm"/>'
                f"</style:style>")
            cols.append(f'<table:table-column table:style-name="{st}"/>')
        self.auto.append(
            f'<style:style style:name="{name}" style:family="table">'
            f'<style:table-properties style:width="{TEXT_WIDTH_CM}cm" '
            f'table:align="center" table:border-model="collapsing"/></style:style>')
        self.auto.append(
            f'<style:style style:name="{name}R" style:family="table-row">'
            f'<style:table-row-properties fo:keep-together="always"/></style:style>')
        self.auto.append(
            f'<style:style style:name="{name}H" style:family="table-cell">'
            f'<style:table-cell-properties fo:background-color="#1f5fa8" fo:padding="0.11cm" '
            f'fo:vertical-align="middle" fo:border="0.5pt solid #1f5fa8"/></style:style>')
        self.auto.append(
            f'<style:style style:name="{name}B" style:family="table-cell">'
            f'<style:table-cell-properties fo:padding="0.10cm" fo:vertical-align="top" '
            f'fo:border="0.5pt solid #d5dae1"/></style:style>')
        self.auto.append(
            f'<style:style style:name="{name}Z" style:family="table-cell">'
            f'<style:table-cell-properties fo:background-color="#f5f8fb" fo:padding="0.10cm" '
            f'fo:vertical-align="top" fo:border="0.5pt solid #d5dae1"/></style:style>')
        head = "".join(
            f'<table:table-cell table:style-name="{name}H" office:value-type="string">'
            f'<text:p text:style-name="TableHead">{_plain(h)}</text:p></table:table-cell>'
            for h in headers)
        body = []
        for i, row in enumerate(rows):
            cell_style = f"{name}Z" if i % 2 else f"{name}B"
            cells = "".join(
                f'<table:table-cell table:style-name="{cell_style}" office:value-type="string">'
                f'{self._p("TableCell", c)}</table:table-cell>' for c in row)
            body.append(f'<table:table-row table:style-name="{name}R">{cells}</table:table-row>')
        self.body.append(self._p("TableCaption", f"**{self.table_word} {self.tab_n}.**  {caption}"))
        self.body.append(
            f'<table:table table:name="{name}" table:style-name="{name}">'
            + "".join(cols)
            + f'<table:table-header-rows><table:table-row table:style-name="{name}R">'
              f"{head}</table:table-row></table:table-header-rows>"
            + "".join(body)
            + "</table:table>")
        if source:
            self.body.append(self._p("Source", source))
        else:
            self.body.append(self._p("Source", ""))

    # ---------------------------------------------------------------- write
    def _toc(self) -> str:
        entries = []
        for level, number, title, anchor in self.headings:
            if level == 1:
                style = "TOC1"
            elif level == 2:
                style = "TOC2"
            else:
                style = "TOC3"
            label = f"{number}  {title}" if number else title
            page = self.pages.get(label)
            tail = ""
            if page is not None:
                tail = (f'<text:tab/>'
                        f'<text:a text:style-name="TOCPage" xlink:type="simple" '
                        f'xlink:href="#{anchor}">{page}</text:a>')
            entries.append(
                f'<text:p text:style-name="{style}">'
                f'<text:a text:style-name="TOCLink" xlink:type="simple" xlink:href="#{anchor}">{_inline(label)}</text:a>'
                f"{tail}</text:p>")
        return ('<text:table-of-content text:name="TOC" text:style-name="TOCTitle">'
                '<text:table-of-content-source text:outline-level="3" '
                'text:use-index-marks="false" text:use-index-source-styles="false"/>'
                '<text:index-body>'
                f'<text:p text:style-name="TOCTitle">{escape(self.toc_title)}</text:p>'
                + "".join(entries) +
                "</text:index-body></text:table-of-content>")

    def save(self, path: str) -> None:
        body = "\n".join(self.body).replace("<!--TOC-->", self._toc())
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<office:document-content {NS} office:version=\"1.2\">"
            f"<office:automatic-styles>{''.join(self.auto)}</office:automatic-styles>"
            f"<office:body><office:text>{body}</office:text></office:body>"
            "</office:document-content>")
        styles = STYLES_XML.replace("@@HEADER@@", escape(self.header))
        meta = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<office:document-meta {NS} office:version="1.2"><office:meta>'
            f"<dc:title>{escape(self.title)}</dc:title>"
            f"<dc:creator>{escape(self.author)}</dc:creator>"
            f"<dc:subject>{escape(self.subject)}</dc:subject>"
            f"<meta:generator>build_report.py</meta:generator>"
            "</office:meta></office:document-meta>")
        settings = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<office:document-settings {NS} office:version="1.2">'
            "<office:settings/></office:document-settings>")

        pictures = getattr(self, "_pictures", [])
        manifest_entries = [
            '<manifest:file-entry manifest:full-path="/" manifest:version="1.2" '
            f'manifest:media-type="{MIMETYPE}"/>',
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>',
        ]
        for _, arc in pictures:
            manifest_entries.append(
                f'<manifest:file-entry manifest:full-path="{arc}" manifest:media-type="image/png"/>')
        manifest = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            + "".join(manifest_entries) + "</manifest:manifest>")

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, zipfile.ZIP_STORED)
            zf.writestr("content.xml", content)
            zf.writestr("styles.xml", styles)
            zf.writestr("meta.xml", meta)
            zf.writestr("settings.xml", settings)
            zf.writestr("META-INF/manifest.xml", manifest)
            for src, arc in pictures:
                with open(src, "rb") as fh:
                    zf.writestr(arc, fh.read(), zipfile.ZIP_DEFLATED)
        print(f"wrote {path}  ({os.path.getsize(path) / 1024:.0f} kB, "
              f"{self.fig_n} figures, {self.tab_n} tables)")


STYLES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles @@NS@@ office:version="1.2">
<office:font-face-decls>
 <style:font-face style:name="DejaVu Sans" svg:font-family="'DejaVu Sans'" style:font-family-generic="swiss" style:font-pitch="variable"/>
 <style:font-face style:name="DejaVu Sans Mono" svg:font-family="'DejaVu Sans Mono'" style:font-family-generic="modern" style:font-pitch="fixed"/>
 <style:font-face style:name="Liberation Serif" svg:font-family="'Liberation Serif'" style:font-family-generic="roman" style:font-pitch="variable"/>
</office:font-face-decls>
<office:styles>
 <style:default-style style:family="paragraph">
  <style:paragraph-properties fo:orphans="2" fo:widows="2" fo:tab-stop-distance="1.0cm"/>
  <style:text-properties style:font-name="Liberation Serif" fo:font-size="10.5pt" fo:language="en" fo:country="GB" fo:hyphenate="false"/>
 </style:default-style>
 <style:default-style style:family="table-cell">
  <style:table-cell-properties fo:padding="0.10cm" fo:border="0.5pt solid #d5dae1"/>
  <style:paragraph-properties fo:margin="0cm"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.6pt"/>
 </style:default-style>
 <style:style style:name="Standard" style:family="paragraph" style:class="text"/>
 <style:style style:name="Body" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.20cm" fo:line-height="130%"/>
  <style:text-properties style:font-name="Liberation Serif" fo:font-size="10.5pt"/>
 </style:style>
 <style:style style:name="Lead" style:family="paragraph" style:parent-style-name="Body">
  <style:paragraph-properties fo:margin-left="0.5cm" fo:margin-bottom="0.35cm" fo:border-left="3pt solid #1f5fa8" fo:padding-left="0.35cm" fo:text-align="left"/>
  <style:text-properties fo:font-size="11.5pt" fo:color="#243b53" fo:font-style="italic"/>
 </style:style>
 <style:style style:name="H1" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
  <style:paragraph-properties fo:margin-top="0.9cm" fo:margin-bottom="0.30cm" fo:keep-with-next="always" fo:border-bottom="0.8pt solid #c9d3e0" fo:padding-bottom="0.12cm"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="17pt" fo:font-weight="bold" fo:color="#1b3a5c"/>
 </style:style>
 <style:style style:name="H2" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
  <style:paragraph-properties fo:margin-top="0.55cm" fo:margin-bottom="0.18cm" fo:keep-with-next="always"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="12.5pt" fo:font-weight="bold" fo:color="#1f5fa8"/>
 </style:style>
 <style:style style:name="H3" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
  <style:paragraph-properties fo:margin-top="0.40cm" fo:margin-bottom="0.12cm" fo:keep-with-next="always"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="10.5pt" fo:font-weight="bold" fo:color="#3c4043"/>
 </style:style>
 <style:style style:name="Title" style:family="paragraph" style:parent-style-name="Standard" style:master-page-name="Standard">
  <style:paragraph-properties fo:margin-top="4.5cm" fo:margin-bottom="0.3cm" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="30pt" fo:font-weight="bold" fo:color="#14304d"/>
 </style:style>
 <style:style style:name="Subtitle" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-bottom="1.0cm" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="13pt" fo:color="#5b6b7c"/>
 </style:style>
 <style:style style:name="CoverMeta" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-bottom="0.10cm" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="9.5pt" fo:color="#4a5a6a"/>
 </style:style>
 <style:style style:name="Rule" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.2cm" fo:margin-bottom="0.6cm" fo:border-bottom="2.5pt solid #1f5fa8"/>
 </style:style>
 <style:style style:name="Bullet" style:family="paragraph" style:parent-style-name="Body">
  <style:paragraph-properties fo:margin-left="0.65cm" fo:text-indent="-0.35cm" fo:margin-bottom="0.12cm"/>
  <style:text-properties fo:font-size="10.3pt"/>
 </style:style>
 <style:style style:name="Numbered" style:family="paragraph" style:parent-style-name="Body">
  <style:paragraph-properties fo:margin-left="0.75cm" fo:text-indent="-0.45cm" fo:margin-bottom="0.12cm"/>
  <style:text-properties fo:font-size="10.3pt"/>
 </style:style>
 <style:style style:name="Caption" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.10cm" fo:margin-bottom="0.45cm" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.4pt" fo:color="#4a5a6a"/>
 </style:style>
 <style:style style:name="TableCaption" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.35cm" fo:margin-bottom="0.12cm" fo:keep-with-next="always"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.8pt" fo:color="#1b3a5c"/>
 </style:style>
 <style:style style:name="Source" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.08cm" fo:margin-bottom="0.42cm"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="7.8pt" fo:color="#6b7280"/>
 </style:style>
 <style:style style:name="Figure" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.35cm" fo:margin-bottom="0.05cm" fo:text-align="center" fo:keep-with-next="always"/>
 </style:style>
 <style:style style:name="CodeBlock" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.15cm" fo:margin-bottom="0.35cm" fo:margin-left="0.05cm" fo:margin-right="0.05cm" fo:text-align="left" fo:line-height="118%" fo:background-color="#eef2f7" fo:border="0.5pt solid #ccd6e2" fo:padding="0.20cm"/>
  <style:text-properties style:font-name="DejaVu Sans Mono" fo:font-size="8.0pt" fo:color="#243b53"/>
 </style:style>
 <style:style style:name="NoteTitle" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.25cm" fo:margin-bottom="0.05cm" fo:padding-left="0.30cm" fo:border-left="3pt solid #c77700"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="9.2pt" fo:font-weight="bold" fo:color="#8a5200"/>
 </style:style>
 <style:style style:name="Note" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-bottom="0.35cm" fo:padding-left="0.30cm" fo:border-left="3pt solid #e8c98f" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="9.2pt" fo:color="#3c4043"/>
 </style:style>
 <style:style style:name="AfterCover" style:family="paragraph" style:parent-style-name="Body" style:master-page-name="Main">
  <style:paragraph-properties fo:break-before="page"/>
 </style:style>
 <style:style style:name="CodeSection" style:family="section">
  <style:section-properties fo:background-color="#eef2f7" fo:padding="0.18cm" fo:border="0.5pt solid #ccd6e2" fo:margin-bottom="0.30cm"/>
 </style:style>
 <style:style style:name="NoteSection" style:family="section">
  <style:section-properties fo:background-color="#fdf6e9" fo:padding="0.10cm" fo:margin-bottom="0.35cm"/>
 </style:style>
 <style:style style:name="TableHead" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin="0cm" fo:text-align="left"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.4pt" fo:font-weight="bold" fo:color="#ffffff"/>
 </style:style>
 <style:style style:name="TableCell" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin="0cm" fo:text-align="left" fo:line-height="115%"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.4pt" fo:color="#1f2933"/>
 </style:style>
 <style:style style:name="CellHead" style:family="table-cell">
  <style:table-cell-properties fo:background-color="#1f5fa8" fo:padding="0.10cm" fo:vertical-align="middle" fo:border="0.5pt solid #1f5fa8"/>
 </style:style>
 <style:style style:name="CellBody" style:family="table-cell">
  <style:table-cell-properties fo:padding="0.10cm" fo:vertical-align="top" fo:border="0.5pt solid #d5dae1" fo:background-color="#ffffff"/>
 </style:style>
 <style:style style:name="TOC1" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.16cm" fo:margin-bottom="0.04cm"><style:tab-stops><style:tab-stop style:position="16.2cm" style:type="right" style:leader-style="dotted" style:leader-text="."/></style:tab-stops></style:paragraph-properties>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="10.2pt" fo:font-weight="bold" fo:color="#1b3a5c"/>
 </style:style>
 <style:style style:name="TOC2" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-left="0.7cm" fo:margin-bottom="0.02cm"><style:tab-stops><style:tab-stop style:position="15.5cm" style:type="right" style:leader-style="dotted" style:leader-text="."/></style:tab-stops></style:paragraph-properties>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="9.2pt" fo:color="#37474f"/>
 </style:style>
 <style:style style:name="TOC3" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-left="1.3cm" fo:margin-bottom="0.02cm"><style:tab-stops><style:tab-stop style:position="14.9cm" style:type="right" style:leader-style="dotted" style:leader-text="."/></style:tab-stops></style:paragraph-properties>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8.6pt" fo:color="#5b6b7c"/>
 </style:style>
 <style:style style:name="TOCTitle" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:margin-top="0.2cm" fo:margin-bottom="0.35cm" fo:border-bottom="0.8pt solid #c9d3e0" fo:padding-bottom="0.10cm"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="16pt" fo:font-weight="bold" fo:color="#1b3a5c"/>
 </style:style>
 <style:style style:name="Header" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:text-align="right" fo:border-bottom="0.5pt solid #d5dae1" fo:padding-bottom="0.05cm"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="7.8pt" fo:color="#7b8794"/>
 </style:style>
 <style:style style:name="Footer" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:text-align="right"/>
  <style:text-properties style:font-name="DejaVu Sans" fo:font-size="8pt" fo:color="#7b8794"/>
 </style:style>
 <style:style style:name="Break" style:family="paragraph" style:parent-style-name="Standard">
  <style:paragraph-properties fo:break-before="page"/>
 </style:style>
 <style:style style:name="Bold" style:family="text">
  <style:text-properties fo:font-weight="bold"/>
 </style:style>
 <style:style style:name="Italic" style:family="text">
  <style:text-properties fo:font-style="italic"/>
 </style:style>
 <style:style style:name="Code" style:family="text">
  <style:text-properties style:font-name="DejaVu Sans Mono" fo:font-size="8.6pt" fo:color="#8a3d1a"/>
 </style:style>
 <style:style style:name="TOCLink" style:family="text">
  <style:text-properties style:text-underline-style="none"/>
 </style:style>
 <style:style style:name="TOCPage" style:family="text">
  <style:text-properties style:text-underline-style="none" fo:font-weight="bold"/>
 </style:style>
 <style:style style:name="Img" style:family="graphic" style:parent-style-name="Graphics">
  <style:graphic-properties style:vertical-pos="top" style:vertical-rel="baseline" style:horizontal-pos="center" style:horizontal-rel="paragraph" style:wrap="none" style:mirror="none"/>
 </style:style>
</office:styles>
<office:automatic-styles>
 <style:page-layout style:name="pm1">
  <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="1.9cm" fo:margin-bottom="1.7cm" fo:margin-left="2.2cm" fo:margin-right="2.2cm" style:writing-mode="lr-tb"/>
  <style:header-style><style:header-footer-properties fo:min-height="0.6cm" fo:margin-bottom="0.35cm"/></style:header-style>
  <style:footer-style><style:header-footer-properties fo:min-height="0.5cm" fo:margin-top="0.35cm"/></style:footer-style>
 </style:page-layout>
 <style:page-layout style:name="pmFirst">
  <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="1.9cm" fo:margin-bottom="1.7cm" fo:margin-left="2.2cm" fo:margin-right="2.2cm" style:writing-mode="lr-tb"/>
 </style:page-layout>
</office:automatic-styles>
<office:master-styles>
 <style:master-page style:name="Standard" style:page-layout-name="pmFirst"/>
 <style:master-page style:name="Main" style:page-layout-name="pm1">
  <style:header>
   <text:p text:style-name="Header">@@HEADER@@</text:p>
  </style:header>
  <style:footer>
   <text:p text:style-name="Footer"><text:page-number text:select-page="current">1</text:page-number></text:p>
  </style:footer>
 </style:master-page>
</office:master-styles>
</office:document-styles>
""".replace("@@NS@@", NS)

