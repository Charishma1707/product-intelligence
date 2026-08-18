import os
from dotenv import load_dotenv
load_dotenv("c:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\.env")

from pipeline.extractor import extract
import logging
logging.basicConfig(level=logging.INFO)

chunks = [{
    "source_type": "pdf_text",
    "text": "SKF Datasheet\nPart Number: 6205-2RS1\nDeep groove ball bearing 25x52x15mm sealed\nBore Diameter 25 mm\nOuter Diameter 52 mm\nWidth 15 mm\n",
    "url": "local",
    "doc_id": "123",
    "doc_name": "SKF.pdf",
    "page_number": 1
}]

fields = ["inner_diameter", "outer_diameter", "width"]
res = extract("SKF", "6205-2RS1", "Deep groove ball bearing", "bearings", fields, chunks)
for k, v in res.items():
    print(k, v.value, v.source_type)
