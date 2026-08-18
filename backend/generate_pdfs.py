import os
from fpdf import FPDF
import csv

pdf_dir = "c:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\sample_data\\reference_docs"
os.makedirs(pdf_dir, exist_ok=True)

samples = [
    ("Siemens", "3RT2015-1BB41", "Contactor 3-pole 7A 24VDC coil", {"Voltage Rating": "230/400 V AC", "Current Rating": "7 A", "Power Rating": "3 kW"}),
    ("Schneider Electric", "LC1D09BD", "TeSys D contactor 3-pole 9A 24VDC coil", {"Voltage Rating": "230/400 V AC", "Current Rating": "9 A", "Coil Voltage": "24 V DC", "Contact Configuration": "3-pole NO"}),
    ("SKF", "6205-2RS1", "Deep groove ball bearing 25x52x15mm sealed", {"Bore Diameter": "25 mm", "Outer Diameter": "52 mm", "Width": "15 mm"}),
    ("FAG", "6204-2Z", "Ball bearing 20x47x14mm shielded", {"Bore Diameter": "20 mm", "Outer Diameter": "47 mm", "Width": "14 mm"}),
    ("Omron", "E2E-X5ME1", "Inductive proximity sensor 5mm sensing distance NPN", {"Sensing Distance": "5 mm", "Output Type": "NPN", "Supply Voltage": "12-24 V DC"}),
    ("Pepperl+Fuchs", "NBB5-18GM50-E0", "Inductive sensor M18 5mm NPN normally open", {"Sensing Distance": "5 mm", "Output Type": "NPN NO", "Supply Voltage": "10-30 V DC"}),
    ("ABB", "AF09-30-10-13", "Contactor 3-pole 9A 100-250V AC/DC coil", {"Voltage Rating": "690 V AC", "Current Rating": "9 A", "Coil Voltage": "100-250 V AC/DC"}),
    ("Honeywell", "922AA1WA-A4", "Limit switch roller lever actuator SPDT", {"Actuator Type": "Roller Lever", "Contact Configuration": "SPDT", "Voltage Rating": "250 V AC"})
]

for brand, mpn, desc, specs in samples:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt=f"{brand} Datasheet", ln=True, align='C')
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, txt=f"Part Number: {mpn}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=desc, ln=True, align='C')
    
    pdf.ln(20)
    pdf.set_font("Arial", size=12)
    
    # Write a table of specs
    for key, value in specs.items():
        pdf.cell(90, 10, txt=key, border=1)
        pdf.cell(90, 10, txt=value, border=1)
        pdf.ln()
        
    pdf_path = os.path.join(pdf_dir, f"{brand}_{mpn}.pdf")
    pdf.output(pdf_path)
    print(f"Generated {pdf_path}")
