"""使用 ReportLab 生成可缩放的 A4 矢量拼豆图纸。"""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from backend.core.bead_generator import PatternResult
from backend.core.statistic import ColorStatistic


def build_pattern_pdf(result: PatternResult, statistics: list[ColorStatistic]) -> bytes:
    buffer = io.BytesIO()
    font_name = _register_document_font()
    document = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    document.setTitle("MARD Bead Pattern")
    document.setAuthor("MARD Bead Pattern Generator")
    _draw_pattern_page(document, result, font_name, show_codes=False)
    document.showPage()
    _draw_pattern_page(document, result, font_name, show_codes=True)
    document.showPage()
    _draw_statistics_pages(document, result, statistics, font_name)
    document.save()
    return buffer.getvalue()


def save_pattern_pdf(
    result: PatternResult,
    statistics: list[ColorStatistic],
    destination: str | Path | BinaryIO,
) -> None:
    payload = build_pattern_pdf(result, statistics)
    if hasattr(destination, "write"):
        destination.write(payload)
    else:
        Path(destination).write_bytes(payload)


def _draw_pattern_page(
    document: canvas.Canvas,
    result: PatternResult,
    font_name: str,
    *,
    show_codes: bool,
) -> None:
    page_width, page_height = A4
    margin = 30.0
    title = "MARD 色号标注图" if show_codes else "MARD 拼豆色块图"
    document.setFillColorRGB(0.06, 0.09, 0.16)
    document.setFont(font_name, 14)
    document.drawString(margin, page_height - 30, title)
    specification = result.specification
    document.setFont(font_name, 8)
    document.drawRightString(
        page_width - margin,
        page_height - 29,
        f"{specification.key} · 板容量 {specification.bead_count} 颗 · "
        f"{specification.width_mm:g} × {specification.height_mm:g} mm",
    )

    matrix = result.mapped.rgb
    codes = result.mapped.codes
    active_mask = result.mapped.active_mask
    rows, columns, _ = matrix.shape
    available_width = page_width - margin * 2
    available_height = page_height - 92
    ruler_size = 18.0
    cell_size = min(
        (available_width - ruler_size) / columns,
        (available_height - ruler_size) / rows,
    )
    pattern_width = cell_size * columns
    pattern_height = cell_size * rows
    block_width = ruler_size + pattern_width
    block_height = ruler_size + pattern_height
    origin_x = (page_width - block_width) / 2 + ruler_size
    origin_y = 38 + (available_height - block_height) / 2

    for row in range(rows):
        y = origin_y + (rows - row - 1) * cell_size
        for column in range(columns):
            if not active_mask[row, column]:
                continue
            document.setFillColor(HexColor(_rgb_to_hex(matrix[row, column])))
            document.rect(origin_x + column * cell_size, y, cell_size, cell_size, stroke=0, fill=1)

    for column in range(columns + 1):
        major = column % 10 == 0
        document.setStrokeColor(Color(0.10, 0.14, 0.23, alpha=0.9 if major else 0.45))
        document.setLineWidth(0.45 if major else 0.12)
        x = origin_x + column * cell_size
        document.line(x, origin_y, x, origin_y + pattern_height)
    for row in range(rows + 1):
        major = row % 10 == 0
        document.setStrokeColor(Color(0.10, 0.14, 0.23, alpha=0.9 if major else 0.45))
        document.setLineWidth(0.45 if major else 0.12)
        y = origin_y + row * cell_size
        document.line(origin_x, y, origin_x + pattern_width, y)

    _draw_pdf_rulers(
        document,
        rows=rows,
        columns=columns,
        origin_x=origin_x,
        origin_y=origin_y,
        cell_size=cell_size,
        ruler_size=ruler_size,
        font_name=font_name,
    )

    if show_codes:
        font_size = min(6.2, max(2.1, cell_size * 0.54))
        document.setFont("Helvetica-Bold", font_size)
        for row in range(rows):
            y = origin_y + (rows - row - 1) * cell_size + (cell_size - font_size) / 2 + 0.4
            for column in range(columns):
                if not active_mask[row, column]:
                    continue
                rgb = tuple(int(value) for value in matrix[row, column])
                if _luminance(rgb) > 0.48:
                    document.setFillColorRGB(0.04, 0.07, 0.13)
                else:
                    document.setFillColorRGB(1, 1, 1)
                document.drawCentredString(
                    origin_x + (column + 0.5) * cell_size,
                    y,
                    str(codes[row, column]),
                )

    document.setFillColorRGB(0.25, 0.29, 0.36)
    document.setFont(font_name, 7)
    document.drawCentredString(page_width / 2, 18, "粗线每 10 格；每格代表一颗 2.6 mm 拼豆")


def _draw_statistics_pages(
    document: canvas.Canvas,
    result: PatternResult,
    statistics: list[ColorStatistic],
    font_name: str,
) -> None:
    page_width, page_height = A4
    margin = 34.0
    row_height = 17.0
    rows_per_page = 39
    total_pages = max(1, (len(statistics) + rows_per_page - 1) // rows_per_page)

    for page_index in range(total_pages):
        if page_index > 0:
            document.showPage()
        document.setFont(font_name, 14)
        document.setFillColorRGB(0.06, 0.09, 0.16)
        document.drawString(margin, page_height - 32, "MARD 拼豆材料清单")
        document.setFont(font_name, 8)
        document.drawRightString(
            page_width - margin,
            page_height - 31,
            f"实际使用 {sum(item.count for item in statistics)} 颗 · 第 {page_index + 1}/{total_pages} 页",
        )

        y = page_height - 60
        columns = (margin, 190, 360, 455)
        headers = ("色号", "HEX", "数量", "占比")
        document.setFillColorRGB(0.08, 0.13, 0.23)
        document.rect(margin, y - 4, page_width - margin * 2, row_height, stroke=0, fill=1)
        document.setFillColorRGB(1, 1, 1)
        document.setFont(font_name, 8)
        for x, header in zip(columns, headers):
            document.drawString(x + 4, y + 1, header)
        y -= row_height

        start = page_index * rows_per_page
        for row_number, item in enumerate(statistics[start : start + rows_per_page]):
            if row_number % 2 == 0:
                document.setFillColorRGB(0.95, 0.97, 0.99)
                document.rect(margin, y - 4, page_width - margin * 2, row_height, stroke=0, fill=1)
            document.setFillColor(HexColor(item.hex))
            document.rect(margin + 4, y, 9, 9, stroke=1, fill=1)
            document.setFillColorRGB(0.08, 0.11, 0.18)
            document.setFont("Helvetica", 7.5)
            document.drawString(columns[0] + 18, y, item.code)
            document.drawString(columns[1] + 4, y, item.hex)
            document.drawRightString(columns[3] - 8, y, str(item.count))
            document.drawRightString(page_width - margin - 5, y, f"{item.percentage:.2f}%")
            y -= row_height


def _draw_pdf_rulers(
    document: canvas.Canvas,
    *,
    rows: int,
    columns: int,
    origin_x: float,
    origin_y: float,
    cell_size: float,
    ruler_size: float,
    font_name: str,
) -> None:
    """绘制与 PNG 一致的顶部列号和左侧行号。"""

    pattern_width = columns * cell_size
    pattern_height = rows * cell_size
    document.setFillColorRGB(0.945, 0.961, 0.976)
    document.rect(origin_x, origin_y + pattern_height, pattern_width, ruler_size, stroke=0, fill=1)
    document.rect(origin_x - ruler_size, origin_y, ruler_size, pattern_height, stroke=0, fill=1)
    document.setFillColorRGB(0.886, 0.91, 0.941)
    document.rect(
        origin_x - ruler_size,
        origin_y + pattern_height,
        ruler_size,
        ruler_size,
        stroke=0,
        fill=1,
    )

    document.setStrokeColorRGB(0.39, 0.455, 0.545)
    for column in range(columns + 1):
        length = 6 if column % 10 == 0 else 4 if column % 5 == 0 else 2
        x = origin_x + column * cell_size
        document.setLineWidth(0.45 if length == 6 else 0.2)
        document.line(x, origin_y + pattern_height, x, origin_y + pattern_height + length)
    for row in range(rows + 1):
        length = 6 if row % 10 == 0 else 4 if row % 5 == 0 else 2
        y = origin_y + pattern_height - row * cell_size
        document.setLineWidth(0.45 if length == 6 else 0.2)
        document.line(origin_x - length, y, origin_x, y)

    font_size = min(6.5, max(3.0, cell_size * 0.68))
    document.setFont(font_name, font_size)
    document.setFillColorRGB(0.2, 0.255, 0.333)
    for column in _ruler_label_indices(columns):
        document.drawCentredString(
            origin_x + (column + 0.5) * cell_size,
            origin_y + pattern_height + (ruler_size - font_size) / 2,
            str(column + 1),
        )
    for row in _ruler_label_indices(rows):
        document.drawRightString(
            origin_x - 7,
            origin_y + pattern_height - (row + 0.5) * cell_size - font_size * 0.35,
            str(row + 1),
        )

    document.setStrokeColorRGB(0.2, 0.255, 0.333)
    document.setLineWidth(0.5)
    document.line(origin_x, origin_y, origin_x, origin_y + pattern_height + ruler_size)
    document.line(
        origin_x - ruler_size,
        origin_y + pattern_height,
        origin_x + pattern_width,
        origin_y + pattern_height,
    )


def _ruler_label_indices(count: int) -> list[int]:
    return sorted({0, count - 1, *range(4, count, 5)})


def _register_document_font() -> str:
    candidates = (
        ("MardCJK", Path("C:/Windows/Fonts/simhei.ttf")),
        ("MardCJK", Path("C:/Windows/Fonts/msyh.ttf")),
        ("MardCJK", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
    )
    for name, path in candidates:
        if not path.exists():
            continue
        try:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            return name
        except Exception:
            continue
    fallback = "STSong-Light"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def _rgb_to_hex(rgb: object) -> str:
    values = [int(value) for value in rgb]
    return f"#{values[0]:02X}{values[1]:02X}{values[2]:02X}"


def _luminance(rgb: tuple[int, int, int]) -> float:
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


__all__ = ["build_pattern_pdf", "save_pattern_pdf"]
