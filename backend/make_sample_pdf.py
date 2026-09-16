"""Creates a small test PDF with Hindi text content for pipeline testing.

Run from backend/:
    python make_sample_pdf.py

Creates: sample_hindi_textbook.pdf (8 pages, ~2 MB)
"""

import sys
from pathlib import Path

import fitz

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/Nirmala.ttc"),
    Path("C:/Windows/Fonts/NirmalaUI.ttf"),
    Path("C:/Windows/Fonts/Nirmala.ttf"),
    Path("C:/Windows/Fonts/Mangal.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
    Path("/usr/share/fonts/truetype/lohit-devanagari/lohit-devanagari.ttf"),
]

LESSON_TEXT = [
    "अध्याय 3 — पौधों में जीवन",
    "",
    "पौधे हमारी पृथ्वी के लिए बहुत महत्वपूर्ण हैं।",
    "वे भोजन और ऑक्सीजन देते हैं।",
    "पौधों के मुख्य अंग होते हैं — जड़, तना, पत्ती, फूल और फल।",
    "",
    "1. जड़: जड़ पौधे को धरती से जल और खनिज लवण देती है।",
    "2. तना: तना पानी और भोजन को पत्तियों तक पहुँचाता है।",
    "3. पत्ती: पत्ती वायु से कार्बन डाइऑक्साइड ग्रहण करती है।",
    "4. फूल: फूल से फल बनता है।",
    "",
    "प्रकाश संश्लेषण की क्रिया में पौधे सूर्य के प्रकाश की ऊर्जा से भोजन बनाते हैं।",
    "इस भोजन में पत्तियाँ हरी हो जाती हैं। इसे हरितलिका कहते हैं।",
    "हरितलिका प्रकाश का अवशोषण करती है।",
]


def main():
    out_path = Path(__file__).resolve().parent / "sample_hindi_textbook.pdf"

    font_path = None
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            font_path = candidate
            break

    if font_path is None:
        print("No Devanagari font found. Skipping PDF creation.")
        print("If you have a Hindi font, place it in the backend/ directory")
        print("or update FONT_CANDIDATES in this file.")
        return

    doc = fitz.open()
    fontname = "hindi"

    for page_no in range(1, 9):
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname=fontname, fontfile=str(font_path))
        lines = [f"पृष्ठ {page_no}", ""] + LESSON_TEXT
        page.insert_textbox(
            fitz.Rect(50, 50, 545, 770),
            "\n".join(lines),
            fontname=fontname,
            fontsize=14,
        )

    doc.save(str(out_path))
    doc.close()
    print(f"Created {out_path.name} ({out_path.stat().st_size // 1024} KB, 8 pages)")


if __name__ == "__main__":
    main()