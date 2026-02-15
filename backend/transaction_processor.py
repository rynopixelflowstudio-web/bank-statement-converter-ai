from typing import List, Dict
import re
from datetime import datetime
from dateutil import parser as date_parser


class TransactionProcessor:
    """Process and normalize extracted transaction data"""
    
    def __init__(self, transactions: List[Dict]):
        self.transactions = transactions
    
    def process(self) -> List[Dict]:
        """Process all transactions"""
        processed = []
        
        for transaction in self.transactions:
            processed_trans = self._process_transaction(transaction)
            if self._is_valid_transaction(processed_trans):
                processed.append(processed_trans)
        
        return processed
    
    def _process_transaction(self, transaction: Dict) -> Dict:
        """Process and CORRECT transaction columns based on signs"""
        raw_debit = transaction.get('debit', '')
        raw_credit = transaction.get('credit', '')
        
        # Sign Detection: If Credit is negative, it's a Debit
        is_neg_debit = '-' in str(raw_debit) or '(' in str(raw_debit)
        is_neg_credit = '-' in str(raw_credit) or '(' in str(raw_credit)
        
        norm_debit = self._normalize_amount(raw_debit)
        norm_credit = self._normalize_amount(raw_credit)
        
        # The Final Column Guard
        final_debit = norm_debit
        final_credit = norm_credit
        
        if (is_neg_credit and norm_credit) or (norm_debit and not norm_credit):
            # Move negative credits OR existing debits to Debit column
            final_debit = norm_debit or norm_credit
            final_credit = ""
        elif is_neg_debit and norm_debit:
            # Move negative debits to Debit (redundant but safe)
            final_debit = norm_debit
            final_credit = ""
            
        return {
            'date': self._normalize_date(transaction.get('date', '')),
            'description': self._clean_description(transaction.get('description', '')),
            'reference': self._clean_reference(transaction.get('reference', '')),
            'debit': final_debit,
            'credit': final_credit,
            'balance': self._normalize_amount(transaction.get('balance', ''))
        }
    
    def _normalize_date(self, date_str: str) -> str:
        """Strict Day-First Normalization for SA Statements"""
        if not date_str or not date_str.strip():
            return ''
        
        date_str = date_str.strip()
        
        # Only use Day-First formats to prevent flipping
        formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
            '%d %b %Y', '%d %B %Y',
            '%d/%m/%y', '%d-%m-%y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%d/%m/%Y')
            except ValueError:
                continue
        
        # Try fuzzy parsing but FORCE dayfirst
        try:
            dt = date_parser.parse(date_str, dayfirst=True)
            return dt.strftime('%d/%m/%Y')
        except:
            pass
        
        return date_str
    
    def _clean_description(self, description: str) -> str:
        """Clean and normalize description text"""
        if not description:
            return ''
        
        # Remove extra whitespace
        description = ' '.join(description.split())
        
        # Remove common noise patterns
        noise_patterns = [
            r'^\s*-\s*',  # Leading dashes
            r'\s*-\s*$',  # Trailing dashes
            r'^\s*\*\s*',  # Leading asterisks
            r'\s{2,}',  # Multiple spaces
        ]
        
        for pattern in noise_patterns:
            description = re.sub(pattern, ' ', description)
        
        # Capitalize properly
        description = description.strip()
        
        # Remove duplicate words
        words = description.split()
        seen = set()
        cleaned_words = []
        for word in words:
            word_lower = word.lower()
            if word_lower not in seen or len(word_lower) <= 2:
                cleaned_words.append(word)
                seen.add(word_lower)
        
        return ' '.join(cleaned_words)
    
    def _clean_reference(self, reference: str) -> str:
        """Clean reference number"""
        if not reference:
            return ''
        
        # Remove whitespace and special characters
        reference = re.sub(r'[^\w\d]', '', reference)
        return reference.strip().upper()
    
    def _normalize_amount(self, amount: str) -> str:
        """Normalize amount to decimal format"""
        if not amount or not str(amount).strip():
            return ''
        
        amount_str = str(amount).strip()
        
        # Remove currency symbols and whitespace
        amount_str = re.sub(r'[R$£€\s]', '', amount_str)
        
        # Handle negative amounts
        is_negative = '-' in amount_str or '(' in amount_str
        
        # Remove non-numeric characters except decimal point and comma
        amount_str = re.sub(r'[^\d,.]', '', amount_str)
        
        # Handle different decimal separators
        # If there are multiple commas or periods, assume the last one is decimal
        if ',' in amount_str and '.' in amount_str:
            # Both comma and period present
            # Check which one appears last
            last_comma = amount_str.rfind(',')
            last_period = amount_str.rfind('.')
            
            if last_period > last_comma:
                # Period is decimal separator, comma is thousands
                amount_str = amount_str.replace(',', '')
            else:
                # Comma is decimal separator, period is thousands
                amount_str = amount_str.replace('.', '').replace(',', '.')
        elif ',' in amount_str:
            # Only comma present
            # If it's the last separator and followed by 2 digits, it's decimal
            comma_count = amount_str.count(',')
            if comma_count == 1 and len(amount_str.split(',')[1]) == 2:
                amount_str = amount_str.replace(',', '.')
            else:
                # It's a thousands separator
                amount_str = amount_str.replace(',', '')
        
        # Convert to float and format
        try:
            value = float(amount_str)
            if is_negative and value > 0:
                value = -value
            
            # Format to 2 decimal places
            return f"{value:.2f}"
        except ValueError:
            return ''
    
    def _is_valid_transaction(self, transaction: Dict) -> bool:
        """Check if transaction has minimum required data"""
        has_date = bool(transaction.get('date'))
        has_description = bool(transaction.get('description'))
        has_amount = bool(transaction.get('debit') or transaction.get('credit') or transaction.get('balance'))
        
        # Valid if:
        # 1. We have a date and either description or amount
        # 2. We have description and amount (even if date is missing)
        return (has_date and (has_description or has_amount)) or (has_description and has_amount)
    
    def get_summary(self) -> Dict:
        """Get summary statistics of processed transactions"""
        if not self.transactions:
            return {
                'total_transactions': 0,
                'total_debits': 0,
                'total_credits': 0,
                'date_range': None
            }
        
        total_debits = 0
        total_credits = 0
        dates = []
        
        for trans in self.transactions:
            debit = trans.get('debit', '')
            credit = trans.get('credit', '')
            
            if debit:
                try:
                    total_debits += abs(float(debit))
                except:
                    pass
            
            if credit:
                try:
                    total_credits += float(credit)
                except:
                    pass
            
            date_str = trans.get('date', '')
            if date_str:
                try:
                    dt = datetime.strptime(date_str, '%d/%m/%Y')
                    dates.append(dt)
                except:
                    pass
        
        date_range = None
        if dates:
            dates.sort()
            date_range = f"{dates[0].strftime('%d/%m/%Y')} - {dates[-1].strftime('%d/%m/%Y')}"
        
        return {
            'total_transactions': len(self.transactions),
            'total_debits': f"{total_debits:.2f}",
            'total_credits': f"{total_credits:.2f}",
            'date_range': date_range
        }
