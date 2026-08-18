import requests
import pymupdf  # PyMuPDF

pdf_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
pdf_path = "dummy.pdf"

print("Downloading dummy PDF...")
response = requests.get(pdf_url)
with open(pdf_path, "wb") as f:
    f.write(response.content)

print(f"Saved to {pdf_path}. Now parsing with PyMuPDF...\n")

# Open the PDF using PyMuPDF (fitz)
doc = pymupdf.open(pdf_path)

print(f"Total Pages: {len(doc)}")
print("--- Page 1 Content ---")

# Extract text from the first page
first_page = doc[0]
text = first_page.get_text("text")

print(text.strip())

doc.close()
