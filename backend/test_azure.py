from pdf_parser import PDFParser
import sys

def test():
    if len(sys.argv) < 2:
        print("Usage: python test_azure.py <path_to_pdf>")
        return
    
    parser = PDFParser(sys.argv[1])
    try:
        transactions = parser._parse_with_azure()
        print(f"Extracted {len(transactions)} transactions")
        for t in transactions[:5]:
            print(t)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
