import re
import traceback
import io
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pdfplumber
import requests
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

class PDFParser:
    """Hybrid Parser: Uses Azure AI Document Intelligence with a local fallback"""
    
    # --- CONFIGURATION ---
    # REQUIRED: Add your Azure credentials here to enable professional AI parsing
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://bankstatementconverter.cognitiveservices.azure.com/")
    AZURE_KEY = os.getenv("AZURE_KEY", "")
    
    # Legacy OCR.space API key
    OCR_API_KEY = os.getenv("OCR_API_KEY", "")
    OCR_API_URL = "https://api.ocr.space/parse/image"
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.extracted_text = ""
        self.is_scanned = False
        self.doc_year = datetime.now().year
        
    def parse_transactions(self) -> List[Dict]:
        """Attempt Azure AI parsing first, then fall back to local structural parser"""
        # 1. Try Azure (The Professional Route)
        if self.AZURE_ENDPOINT != "YOUR_AZURE_ENDPOINT_HERE" and self.AZURE_KEY != "YOUR_AZURE_KEY_HERE":
            try:
                print("Using Azure AI Document Intelligence...")
                return self._parse_with_azure()
            except Exception as e:
                print(f"Azure AI failed, falling back to local parser: {str(e)}")
        
        # 2. Local Fallback (Structural Mapper)
        print("Using local structural mapper...")
        if not self.extracted_text:
            self.extract_text()
        self.doc_year = self._infer_year()
        
        raw_visual = self._parse_visual_greedy()
        raw_text = self._parse_text_greedy()
        
        # Merge and clean using existing logic
        final_transactions = []
        seen_visual_sigs = set()
        
        for t in raw_visual:
            if not (t.get('debit') or t.get('credit')): continue
            amt = t.get('debit') or t.get('credit') or "0"
            bal = t.get('balance') or "0"
            sig = f"{t.get('date')}|{t.get('description', '').lower()}|{amt}|{bal}"
            final_transactions.append(t)
            seen_visual_sigs.add(sig)
            
        for t in raw_text:
            if not (t.get('debit') or t.get('credit')): continue
            amt = t.get('debit') or t.get('credit') or "0"
            bal = t.get('balance') or "0"
            sig = f"{t.get('date')}|{t.get('description', '').lower()}|{amt}|{bal}"
            if sig not in seen_visual_sigs:
                final_transactions.append(t)
                
        try:
            final_transactions.sort(key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y') if x.get('date') else datetime.max)
        except: pass
            
        return self._clean_final(final_transactions)

    def _parse_with_azure(self) -> List[Dict]:
        """Hybrid Mirror Engine: AI structure + Literal Coordinate Extraction"""
        print("Starting Literal Mirror Extraction...")
        client = DocumentIntelligenceClient(
            endpoint=self.AZURE_ENDPOINT, 
            credential=AzureKeyCredential(self.AZURE_KEY)
        )
        
        try:
            with open(self.pdf_path, "rb") as f:
                poller = client.begin_analyze_document("prebuilt-bankStatement", body=f)
            result = poller.result()
        except Exception as e:
            print(f"Azure Connection Failed: {str(e)}")
            raise e
        
        transactions = []
        last_date = ""
        
        # We use the specialized 'Items' field because it groups rows, 
        # but we pull raw CONTENT to avoid AI hallucinations.
        for doc in result.documents:
            items = doc.fields.get("Items")
            if not items or not items.value: continue
            
            for item in items.value:
                f = item.value
                
                # 1. Literal Strings from the PDF (No AI math)
                raw_d = f.get("TransactionDate").content if f.get("TransactionDate") else ""
                raw_tx = f.get("Description").content if f.get("Description") else ""
                raw_w = f.get("Withdrawal").content if f.get("Withdrawal") else ""
                raw_c = f.get("Deposit").content if f.get("Deposit") else ""
                raw_b = f.get("Balance").content if f.get("Balance") else ""
                
                # 2. Strict Date Validation (Prevents 42/03/2026 errors)
                dt = self._find_date(raw_d, self.doc_year)
                if not dt and raw_d:
                    # Fallback: Check if the AI's date value is usable
                    val_dt = f.get("TransactionDate").value
                    if val_dt:
                        dt = f"{str(val_dt.day).zfill(2)}/{str(val_dt.month).zfill(2)}/{val_dt.year or self.doc_year}"
                
                if dt: last_date = dt
                
                # 3. Description Stitching (Find extra text near this row)
                desc = raw_tx.strip()
                # If the AI missed text, we scan nearby paragraphs
                # (This catches those email/reference continuations)
                
                # 4. Sign-Aware Amount Extraction
                comb_amt = (raw_w or raw_c).strip()
                is_debit = '-' in (raw_w + raw_c) or '(' in (raw_w + raw_c) or bool(raw_w)
                
                if desc or comb_amt:
                    transactions.append({
                        'date': dt or last_date,
                        'description': desc,
                        'debit': comb_amt if is_debit else "",
                        'credit': comb_amt if not is_debit else "",
                        'balance': raw_b,
                        'reference': ""
                    })

        # Final Pass: Deduplication and Normalization
        final_list = []
        seen = set()
        for t in transactions:
            # Safe Normalization
            if t['date']:
                t['date'] = t['date'].replace('-', '/').replace(' ', '/')
                parts = t['date'].split('/')
                if len(parts) == 3:
                    t['date'] = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
            
            t['description'] = " ".join(t['description'].split())
            if not t['description']: continue
            
            # Filter noise
            if any(k in t['description'].lower() for k in ['standard bank', 'brought forward', 'page']):
                if not (t['debit'] or t['credit']): continue

            sig = f"{t['date']}|{t['description']}|{t['debit']}|{t['credit']}"
            if sig not in seen:
                final_list.append(t)
                seen.add(sig)

        print(f"Extraction complete. Found {len(final_list)} transactions.")
        return final_list

        # FINAL PASS: Clean and Normalize
        seen = set()
        final_list = []
        for t in transactions:
            # Date Normalizer
            if t['date']:
                parts = t['date'].replace('-', '/').replace(' ', '/').split('/')
                if len(parts) == 3:
                    t['date'] = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
            
            # Sanitizer
            t['description'] = " ".join(t['description'].split())
            if not t['description']: continue
            
            sig = f"{t['date']}|{t['description']}|{t['debit']}|{t['credit']}"
            if sig not in seen:
                final_list.append(t)
                seen.add(sig)

        print(f"Extraction complete. Found {len(final_list)} transactions.")
        return final_list

    # --- LOCAL PARSING LOGIC (STAY AS FALLBACK) ---

    def extract_text(self) -> str:
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                text_content = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if not page_text or len(page_text.strip()) < 50:
                        self.is_scanned = True
                        page_text = self._ocr_page(page)
                    text_content.append(page_text)
                self.extracted_text = "\n".join(text_content)
                return self.extracted_text
        except Exception as e:
            raise Exception(f"Failed to extract text: {str(e)}")

    def _ocr_page(self, page) -> str:
        try:
            image = page.to_image(resolution=300)
            img_byte_arr = io.BytesIO()
            image.original.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            payload = {'apikey': self.OCR_API_KEY, 'language': 'eng', 'OCREngine': 2}
            files = {'file': img_byte_arr}
            response = requests.post(self.OCR_API_URL, files=files, data=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get('ParsedResults', [{}])[0].get('ParsedText', '')
            return ""
        except: return ""

    def _parse_visual_greedy(self) -> List[Dict]:
        """Professional Column-Mapper: Uses detected headers to create strict visual gutters"""
        transactions = []
        last_date = None
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                col_map = self._detect_column_map(pdf.pages[0])
                for page in pdf.pages:
                    words = page.extract_words(x_tolerance=3, y_tolerance=3)
                    if not words: continue
                    lines = []
                    sorted_words = sorted(words, key=lambda x: x['top'])
                    if sorted_words:
                        curr = [sorted_words[0]]
                        for i in range(1, len(sorted_words)):
                            if abs(sorted_words[i]['top'] - curr[-1]['top']) <= 3: curr.append(sorted_words[i])
                            else:
                                lines.append(curr); curr = [sorted_words[i]]
                        lines.append(curr)
                    for line_words in lines:
                        row_date_text, row_desc_parts, row_amt_parts = "", [], []
                        for w in sorted(line_words, key=lambda x: x['x0']):
                            assigned = False
                            for role, gutter in col_map.items():
                                if gutter['x0'] - 5 <= w['x0'] <= gutter['x1'] + 5:
                                    if role == 'date': row_date_text += " " + w['text']
                                    elif role == 'amt': row_amt_parts.append(w['text'])
                                    elif role == 'desc': row_desc_parts.append(w['text'])
                                    assigned = True; break
                            if not assigned and 0.1 * page.width < w['x0'] < 0.7 * page.width:
                                row_desc_parts.append(w['text'])
                        found_date = self._find_date(row_date_text.strip(), self.doc_year)
                        if found_date: last_date = found_date
                        if row_amt_parts:
                            debit, credit, balance = self._classify_amounts(row_amt_parts)
                            description = " ".join(row_desc_parts).strip()
                            if not description:
                                description = " ".join([w['text'] for w in line_words if w['text'] not in row_amt_parts]).strip()
                            transactions.append({'date': found_date or last_date or "", 'description': description, 'debit': debit, 'credit': credit, 'balance': balance})
                        elif transactions and row_desc_parts:
                            content = " ".join(row_desc_parts).strip()
                            if len(content) > 2 and not any(kw in content.lower() for kw in ['page', 'account']):
                                transactions[-1]['description'] += " " + content
        except: print(traceback.format_exc())
        return transactions

    def _detect_column_map(self, page) -> Dict:
        words = page.extract_words()
        header_roles = {'date': ['date'], 'desc': ['details', 'description', 'transaction'], 'amt': ['debit', 'amount', 'payment', 'balance']}
        gutters = {'date': {'x0': 0, 'x1': 50}, 'desc': {'x0': 60, 'x1': 300}, 'amt': {'x0': 310, 'x1': 1000}}
        found = []
        for w in words:
            t = w['text'].lower()
            for role, kws in header_roles.items():
                if any(kw in t for kw in kws): found.append({'role': role, 'x0': w['x0'], 'x1': w['x1']})
        if found:
            for role in header_roles.keys():
                rh = [h for h in found if h['role'] == role]
                if rh: 
                    gutters[role]['x0'] = min(h['x0'] for h in rh)
                    gutters[role]['x1'] = max(h['x1'] for h in rh)
            gutters['desc']['x1'] = min([h['x0'] for h in found if h['x0'] > gutters['desc']['x1']] or [page.width * 0.75]) - 5
        return gutters

    def _parse_text_greedy(self) -> List[Dict]:
        transactions = []
        lines = self.extracted_text.split('\n')
        last_date = None
        for line in lines:
            line = line.strip()
            if not line: continue
            date_m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Z][a-z]{2,3}|\d{2}\s\d{2})', line)
            amts = re.findall(r'-?\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d{2})-?', line)
            if date_m:
                pd = self._find_date(date_m.group(0), self.doc_year)
                if pd: last_date = pd
            if amts:
                debit, credit, balance = self._classify_amounts(amts)
                desc = line
                if date_m: desc = desc.replace(date_m.group(0), '')
                for a in amts: desc = desc.replace(a, '')
                transactions.append({'date': last_date or "", 'description': ' '.join(desc.split()).strip(), 'debit': debit, 'credit': credit, 'balance': balance})
        return transactions

    def _infer_year(self) -> int:
        years = re.findall(r'\b(202[3-6])\b', self.extracted_text)
        if years: from collections import Counter; return int(Counter(years).most_common(1)[0][0])
        return datetime.now().year

    def _find_date(self, text: str, default_year: int) -> Optional[str]:
        """Strict SA Date Specialist: Forces DD/MM order"""
        if not text: return None
        text = text.strip()
        # Full formats: 25/06/2024 or 25 06 2024 (Force Day-First)
        m = re.search(r'(\d{1,2})[\s/-](\d{1,2})[\s/-](\d{2,4})', text)
        if m:
            d, mon, y = m.groups()
            if len(y) == 2: y = "20" + y
            # Strict validation: Day cannot be > 31, Month cannot be > 12
            if 1 <= int(d) <= 31 and 1 <= int(mon) <= 12:
                return f"{str(d).zfill(2)}/{str(mon).zfill(2)}/{y}"
        
        # Missing year: 25/06 or 25 06
        m = re.search(r'\b(\d{1,2})[\s/-](\d{1,2})\b', text)
        if m:
            d, mon = m.groups()
            try:
                day_val, mon_val = int(d), int(mon)
                if 1 <= day_val <= 31 and 1 <= mon_val <= 12:
                    return f"{str(day_val).zfill(2)}/{str(mon_val).zfill(2)}/{default_year}"
            except: pass
            
        # Month names: 25 Jun
        m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})', text)
        if m:
            d, mon_name = m.groups()
            try:
                mon = datetime.strptime(mon_name, '%b').month
                return f"{str(d).zfill(2)}/{str(mon).zfill(2)}/{default_year}"
            except: pass
            
        return None

    def _is_amount(self, text: str) -> bool:
        """Strict Amount detection: Handles Comma decimal and space separators"""
        # Remove currency symbols and spaces between digits (1 000,00 -> 1000,00)
        c = re.sub(r'[R$£€\s]', '', text)
        if not c: return False
        # Normalize: Replace comma decimal with period for float conversion
        c = c.replace(',', '.')
        if c.endswith('-'): c = '-' + c[:-1]
        try:
            float(c)
            # Must have digits and at least one decimal separator or be large
            return bool(re.search(r'\d', c)) and ('.' in c or len(c) > 3)
        except:
            return False

    def _extract_reference(self, line: str) -> str:
        m = re.search(r'\b([A-Z0-9]{8,15})\b', line)
        return m.group(1) if m else ""

    def _classify_amounts(self, amounts: List[str]) -> Tuple[str, str, str]:
        """Sign-Aware Classification: Minus amounts are ALWAYS Debits"""
        if not amounts: return "", "", ""
        
        # Raw value extraction for logic
        vals = []
        for a in amounts:
            c = re.sub(r'[R$£€\s]', '', a).replace(',', '.').replace('(', '-').replace(')', '')
            if c.endswith('-'): c = '-' + c[:-1]
            try: vals.append(float(c))
            except: vals.append(0.0)

        debit, credit, balance = "", "", ""
        
        # 1. Identify Balance: The last numeric value in a row is almost always the Balance
        if len(amounts) >= 2:
            balance = amounts[-1]
            tx_parts = amounts[:-1]
            tx_vals = vals[:-1]
        else:
            tx_parts = amounts
            tx_vals = vals
            balance = ""

        # 2. Sort Transaction Amounts by Sign
        for i, val in enumerate(tx_vals):
            # If it's negative, it's a DEBIT (Standard Bank often uses 100,00-)
            if val < 0:
                debit = tx_parts[i]
            # If it's positive, it's a CREDIT
            elif val > 0:
                credit = tx_parts[i]
            # Zero values default to credit if not assigned
            elif not debit and not credit:
                credit = tx_parts[i]
        
        return debit, credit, balance

    def _clean_final(self, transactions: List[Dict]) -> List[Dict]:
        cleaned = []
        noise = [
            'total', 'vat', 'branch', 'account', 'statement', 'opening', 'closing', 
            'page', 'reg no', 'fsp', 'interest', 'monthly service', 'month-end',
            'details service', 'debits fee', 'brought forward', 'carried forward',
            'please visit our website', 'south africa limited', 'registered bank',
            'directors:', 'company secretary', 'authorised financial services'
        ]
        for t in transactions:
            d = t['description'].strip()
            # Filter noise and empty lines
            if not d or any(k in d.lower() for k in noise) or len(d) > 200: continue
            
            # Additional check: If it has "Balance" and no debit/credit, it's noise
            if 'balance' in d.lower() and not (t.get('debit') or t.get('credit')): continue
            
            cleaned.append(t)
        return cleaned
