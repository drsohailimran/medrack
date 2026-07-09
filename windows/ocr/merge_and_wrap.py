"""
Merge Marker OCR output over RapidOCR cache, then wrap into text-layer PDF.
"""
import os
import re
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

# Paths
scratchpad = Path(r"C:\Users\Sohail Imran\AppData\Local\Temp\claude\C--Medrack\0d804f8c-d675-41fe-889a-3f0e94826bf2\scratchpad")
rapidocr_cache = scratchpad / "parks_ocr_cache"
marker_out = scratchpad / "marker_out"
merged_output = scratchpad / "parks_merged"
output_pdf = scratchpad / "parks_clean_text_layer.pdf"

# Create output directory
merged_output.mkdir(parents=True, exist_ok=True)

print("=== Step 1: Merge Marker over RapidOCR ===")

# Marker chapter mappings (page ranges from marker filenames)
marker_files = {
    "NCD_Epidemiology": (419, 440),
    "Health_Programmes": (503, 528),
    "RCH_PrevMed": (595, 618),
    "Community_Care": (713, 727),
    "Hospital_Waste": (913, 929),
    "Biostatistics": (974, 987),
    "Health_Planning": (999, 1011)
}

# Read all Marker content
marker_content = {}
for chapter, (start, end) in marker_files.items():
    marker_file = marker_out / f"marker_{start:04d}-{end:04d}_{chapter}.md"
    if marker_file.exists():
        content = marker_file.read_text(encoding='utf-8')
        marker_content[chapter] = content
        print(f"  Loaded {chapter}: {len(content)} chars")

# Distribute Marker content evenly across page ranges
page_to_text = {}
for chapter, (start, end) in marker_files.items():
    if chapter in marker_content:
        content = marker_content[chapter]
        num_pages = end - start + 1
        # Split content into roughly equal chunks for each page
        chunk_size = len(content) // num_pages
        for i in range(num_pages):
            page_num = start + i
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size if i < num_pages - 1 else len(content)
            page_to_text[page_num] = content[start_idx:end_idx].strip()

print(f"\n  Mapped {len(page_to_text)} pages from Marker output")

# Merge: use Marker for table chapters, RapidOCR for everything else
merged_count = 0
marker_used = 0
rapidocr_used = 0
empty_pages = 0

for page_num in range(1052):  # 0-1051
    rapidocr_file = rapidocr_cache / f"page_{page_num:04d}.txt"
    output_file = merged_output / f"page_{page_num:04d}.txt"
    
    if page_num in page_to_text:
        # Use Marker output (table-aware)
        output_file.write_text(page_to_text[page_num], encoding='utf-8')
        marker_used += 1
    elif rapidocr_file.exists():
        # Use RapidOCR output
        content = rapidocr_file.read_text(encoding='utf-8')
        output_file.write_text(content, encoding='utf-8')
        if content.strip():
            rapidocr_used += 1
        else:
            empty_pages += 1
    else:
        # Empty page
        output_file.write_text("", encoding='utf-8')
        empty_pages += 1
    
    merged_count += 1

print(f"\nMerged {merged_count} pages:")
print(f"  - Marker (table-aware): {marker_used} pages")
print(f"  - RapidOCR: {rapidocr_used} pages")
print(f"  - Empty/blank: {empty_pages} pages")

print("\n=== Step 2: Wrap into text-layer PDF ===")

# Read original PDF
source_pdf = Path(r"C:\Users\Sohail Imran\Downloads\parks-textbook-of-preventive-and-social-medicine-27nbsped-9382219196-9789382219194_compress.pdf")
print(f"  Reading source PDF: {source_pdf.name}")

reader = PdfReader(str(source_pdf))
writer = PdfWriter()

print(f"  Processing {len(reader.pages)} pages...")

for page_num in range(len(reader.pages)):
    # Get original page
    original_page = reader.pages[page_num]
    
    # Get merged text
    text_file = merged_output / f"page_{page_num:04d}.txt"
    text_content = text_file.read_text(encoding='utf-8').strip() if text_file.exists() else ""
    
    if text_content:
        # Create text overlay PDF in memory
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        
        # Add invisible text (white text, will be searchable but not visible)
        c.setFillColorRGB(1, 1, 1)  # White text
        c.setFont("Helvetica", 8)
        
        # Split text into lines and add to canvas
        lines = text_content.split('\n')
        y_position = 750  # Start from top
        for line in lines[:50]:  # Limit lines to avoid overflow
            if y_position < 50:
                break
            c.drawString(50, y_position, line[:80])  # Limit line length
            y_position -= 12
        
        c.save()
        packet.seek(0)
        
        # Read the text overlay
        text_reader = PdfReader(packet)
        text_page = text_reader.pages[0]
        
        # Merge text layer onto original page
        original_page.merge_page(text_page)
    
    writer.add_page(original_page)
    
    if (page_num + 1) % 100 == 0:
        print(f"    Processed {page_num + 1}/{len(reader.pages)} pages...")

# Write output PDF
print(f"  Writing output PDF: {output_pdf.name}")
with open(output_pdf, 'wb') as output_file:
    writer.write(output_file)

print(f"\nComplete!")
print(f"  Output: {output_pdf}")
print(f"  Size: {output_pdf.stat().st_size / 1024 / 1024:.1f} MB")
print(f"\nNext step: Transfer this PDF to Linux and run:")
print(f"  medrack ingest-book {output_pdf} --subject psm --book 'Parks PSM (clean OCR)'")
