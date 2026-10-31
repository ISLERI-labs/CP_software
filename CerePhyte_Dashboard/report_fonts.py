"""Local, embeddable typography shared by PDF report workflows."""

from pathlib import Path


def register_report_fonts():
    """Register Matplotlib's locally bundled DejaVu fonts with ReportLab."""
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_directory = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    font_files = {
        "CerePhyteMono": "DejaVuSansMono.ttf",
        "CerePhyteMono-Bold": "DejaVuSansMono-Bold.ttf",
        "CerePhyteSans": "DejaVuSans.ttf",
        "CerePhyteSans-Bold": "DejaVuSans-Bold.ttf",
    }

    for font_name, filename in font_files.items():
        if font_name in pdfmetrics.getRegisteredFontNames():
            continue
        font_path = font_directory / filename
        if not font_path.is_file():
            raise RuntimeError(f"Required local report font is missing: {font_path}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

    pdfmetrics.registerFontFamily(
        "CerePhyteMono",
        normal="CerePhyteMono",
        bold="CerePhyteMono-Bold",
        italic="CerePhyteMono",
        boldItalic="CerePhyteMono-Bold",
    )
    pdfmetrics.registerFontFamily(
        "CerePhyteSans",
        normal="CerePhyteSans",
        bold="CerePhyteSans-Bold",
        italic="CerePhyteSans",
        boldItalic="CerePhyteSans-Bold",
    )
    return {
        "mono": "CerePhyteMono",
        "mono_bold": "CerePhyteMono-Bold",
        "sans": "CerePhyteSans",
        "sans_bold": "CerePhyteSans-Bold",
    }
