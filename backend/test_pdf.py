import fitz
doc = fitz.open("C:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\sample_data\\reference_docs\\SKF_6205-2RS1.pdf")
for page in doc:
    print(page.get_text())
