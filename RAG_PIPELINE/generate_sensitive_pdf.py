from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CONFIDENTIAL: Employee Records', 0, 1, 'C')
        self.ln(10)

def create_sensitive_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    data = [
        "Employee: Sarah Connor",
        "Phone: 555-0199",
        "Email: sarah.connor@skynet.com",
        "SSN: 123-45-6789",
        "Credit Card: 4111-1111-1111-1111",
        "",
        "Employee: John Smith",
        "Phone: 555-0123",
        "Email: j.smith@example.com",
        "SSN: 987-65-4320"
    ]

    pdf.cell(0, 10, "Employee Data Table", 0, 1)
    
    for line in data:
        pdf.cell(0, 10, line, 0, 1)

    pdf.output("Sensitive_Data_Test.pdf")
    print("PDF Generated: Sensitive_Data_Test.pdf")

if __name__ == "__main__":
    create_sensitive_pdf()
