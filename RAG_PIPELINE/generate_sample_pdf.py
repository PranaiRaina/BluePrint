from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Financial Overview: Bob Jones', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_sample_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Executive Summary
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "1. Executive Summary", 0, 1)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, "Bob Jones is currently in a strong financial position with a total net worth of $1,250,000. His portfolio is heavily weighted towards technology stocks (45%) and real estate (30%). The primary financial goal for Q1 2026 is to diversify into bonds and reduce high-interest liabilities.")
    pdf.ln(5)

    # Net Worth Statement
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "2. Net Worth Statement (As of Jan 2026)", 0, 1)
    pdf.set_font("Arial", size=12)
    
    data = [
        ("Assets", ""),
        ("  - Primary Residence", "$600,000"),
        ("  - 401(k) Retirement", "$450,000"),
        ("  - Brokerage Account", "$250,000"),
        ("  - Cash / Savings", "$50,000"),
        ("Total Assets", "$1,350,000"),
        ("", ""),
        ("Liabilities", ""),
        ("  - Mortgage Balance", "$80,000"),
        ("  - Car Loan", "$20,000"),
        ("Total Liabilities", "$100,000"),
        ("", ""),
        ("TOTAL NET WORTH", "$1,250,000")
    ]
    
    for item, value in data:
        pdf.cell(100, 10, item, 0, 0)
        pdf.cell(0, 10, value, 0, 1)
    pdf.ln(5)

    # Portfolio Breakthrough
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "3. Investment Portfolio Breakdown", 0, 1)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, "The brokerage account ($250,000) consists of the following holdings:\n- NVDA (NVIDIA Corp): 300 shares @ $900 -> $270,000 (Warning: Overconcentration)\n- AAPL (Apple Inc): 500 shares @ $180 -> $90,000\n- VTI (Vanguard Total Stock): 400 shares @ $250 -> $100,000")
    pdf.ln(5)

    # Recommendations
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "4. Recommendations", 0, 1)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, "- Rebalance Portfolio: Your exposure to NVDA is extremely high. Consider selling 50% of the position to buy BND (Vanguard Total Bond Market).\n- Pay off Car Loan: With $50,000 in cash, pay off the $20,000 car loan (6% APR) immediately to save on interest.\n- Estate Planning: Update beneficiaries on the 401(k) account.")

    pdf.output("Bob_Jones_Financial_Report.pdf")
    print("PDF Generated: Bob_Jones_Financial_Report.pdf")

if __name__ == "__main__":
    create_sample_pdf()
