"""
Content-based file type detection for automatic routing.
"""
import os
import pandas as pd
from typing import Optional
from enum import Enum
import io
import pdfplumber


class FileType(Enum):
    """Supported file types."""
    PROPERTY_SCHEDULE = "property_schedule"
    EPC_DATA = "epc_data"
    FRA_DOCUMENT = "fra_document"
    FRSA_DOCUMENT = "frsa_document"
    FRAEW_DOCUMENT = "fraew_document"  # PAS 9980 - Fire Risk Appraisal of External Walls
    SCR_DOCUMENT = "scr_document"  # Safety Case Report
    UNKNOWN = "unknown"


class FileTypeDetector:
    """Detects file type based on content and filename."""
    
    # Keywords for property schedule detection
    PROPERTY_KEYWORDS = [
        'property', 'address', 'uprn', 'postcode', 'tenure',
        'unit_type', 'block', 'sov', 'schedule', 'portfolio'
    ]
    
    # Keywords for EPC data detection
    EPC_KEYWORDS = [
        'epc', 'energy', 'rating', 'efficiency', 'performance',
        'certificate', 'sap', 'rdsap'
    ]
    
    # Keywords for FRA detection (Fire Risk Assessment)
    FRA_KEYWORDS = [
        'fra', 'fire risk assessment', 'fire_risk_assessment'
    ]
    
    # Keywords for FRSA detection (Fire Risk Safety Assessment)
    FRSA_KEYWORDS = [
        'frsa', 'fire risk safety assessment', 'fire_risk_safety_assessment'
    ]
    
    # Keywords for FRAEW detection (PAS 9980 - Fire Risk Appraisal of External Walls)
    FRAEW_KEYWORDS = [
        'fraew', 'pas 9980', 'pas9980', 'fire risk appraisal', 'external walls',
        'external_walls', 'wall appraisal', 'wall_appraisal', '9980'
    ]
    
    # Keywords for SCR detection (Safety Case Report)
    SCR_KEYWORDS = [
        'scr', 'safety case', 'safety_case', 'safety case report', 'safety_case_report'
    ]
    
    # General fire/safety keywords (for fallback detection)
    FIRE_SAFETY_KEYWORDS = [
        'fire', 'risk', 'assessment', 'safety', 'appraisal'
    ]
    
    def detect_file_type(
        self,
        filename: str,
        file_content: Optional[bytes] = None,
    ) -> FileType:
        """
        Detect file type from filename and/or content.
        
        Args:
            filename: File name
            file_content: Optional file content bytes
            
        Returns:
            Detected FileType
        """
        ext = os.path.splitext(filename)[1].lower()
        
        # For PDFs, prioritize content analysis over filename
        if ext == '.pdf':
            # First try content-based detection if file content is available
            if file_content:
                try:
                    pdf_type = self.detect_file_type_from_pdf_content(file_content, filename)
                    if pdf_type != FileType.UNKNOWN:
                        return pdf_type
                except Exception:
                    # If PDF extraction fails, fall back to filename
                    pass
            
            # Fall back to filename-based detection
            pdf_type = self.detect_file_type_from_filename(filename)
            if pdf_type != FileType.UNKNOWN:
                return pdf_type
            # Default PDFs to FRA if unclear
            return FileType.FRA_DOCUMENT
        
        # For CSV/Excel, try filename first (quick check), then content analysis
        if ext in ['.csv', '.xlsx', '.xls']:
            # Quick filename check first
            filename_type = self.detect_file_type_from_filename(filename)
            if filename_type != FileType.UNKNOWN:
                return filename_type
            
            # Then try content-based detection if available
            if file_content:
                try:
                    return self.detect_file_type_from_content(file_content, filename, ext)
                except Exception:
                    # If content analysis fails, fall back to default
                    pass
            
            # Default CSV/Excel to property schedule
            return FileType.PROPERTY_SCHEDULE
        
        # Default fallback for unknown extensions
        return FileType.UNKNOWN
    
    def detect_file_type_from_filename(self, filename: str) -> FileType:
        """
        Detect file type from filename patterns.
        
        Args:
            filename: File name (case-insensitive)
            
        Returns:
            Detected FileType
        """
        filename_lower = filename.lower()
        
        # Check for FRAEW keywords (PAS 9980) - check first as it's most specific
        if any(keyword in filename_lower for keyword in self.FRAEW_KEYWORDS):
            return FileType.FRAEW_DOCUMENT
        
        # Check for SCR keywords (Safety Case Report) - check before general fire keywords
        if any(keyword in filename_lower for keyword in self.SCR_KEYWORDS):
            return FileType.SCR_DOCUMENT
        
        # Check for FRSA keywords (more specific than FRA)
        if any(keyword in filename_lower for keyword in self.FRSA_KEYWORDS):
            return FileType.FRSA_DOCUMENT
        
        # Check for FRA keywords (Fire Risk Assessment)
        if any(keyword in filename_lower for keyword in self.FRA_KEYWORDS):
            return FileType.FRA_DOCUMENT
        
        # Check for EPC keywords
        if any(keyword in filename_lower for keyword in self.EPC_KEYWORDS):
            return FileType.EPC_DATA
        
        # Check for property schedule keywords
        if any(keyword in filename_lower for keyword in self.PROPERTY_KEYWORDS):
            return FileType.PROPERTY_SCHEDULE
        
        return FileType.UNKNOWN
    
    def detect_file_type_from_content(
        self,
        file_content: bytes,
        filename: str,
        extension: str,
    ) -> FileType:
        """
        Detect file type by analyzing file content.
        
        Args:
            file_content: File content bytes
            filename: File name
            extension: File extension
            
        Returns:
            Detected FileType
        """
        # Read into DataFrame
        df = self._read_to_dataframe(file_content, extension)
        if df is None or df.empty:
            return FileType.UNKNOWN
        
        return self.detect_file_type_from_dataframe(df, filename)
    
    def detect_file_type_from_dataframe(
        self,
        df: pd.DataFrame,
        filename: str,
    ) -> FileType:
        """
        Detect file type by analyzing DataFrame columns and content.
        
        Args:
            df: Pandas DataFrame
            filename: File name for context
            
        Returns:
            Detected FileType
        """
        if df.empty:
            return FileType.UNKNOWN
        
        columns_lower = [col.lower() for col in df.columns]
        
        # Check for EPC-specific columns
        epc_indicators = [
            'epc_rating', 'epc rating', 'energy_rating', 'energy rating',
            'current_energy_rating', 'energy_efficiency', 'sap_rating'
        ]
        if any(indicator in col for col in columns_lower for indicator in epc_indicators):
            return FileType.EPC_DATA
        
        # Check for EPC rating values in data (A-G)
        for col in df.columns:
            if df[col].dtype == 'object':
                sample_values = df[col].dropna().astype(str).str.upper()
                if sample_values.str.match(r'^[A-G]$').sum() / len(sample_values) > 0.3:
                    # 30%+ of values are A-G ratings
                    if 'epc' in col.lower() or 'energy' in col.lower() or 'rating' in col.lower():
                        return FileType.EPC_DATA
        
        # Check for property schedule indicators
        property_indicators = [
            'uprn', 'address', 'postcode', 'property_id', 'property id',
            'tenure', 'unit_type', 'unit type', 'block_id', 'block id'
        ]
        property_score = sum(
            1 for indicator in property_indicators
            if any(indicator in col for col in columns_lower)
        )
        
        # If we have multiple property indicators, it's likely a property schedule
        if property_score >= 2:
            return FileType.PROPERTY_SCHEDULE
        
        # Check for postcode pattern in data
        for col in df.columns:
            if 'postcode' in col.lower() or 'post_code' in col.lower():
                sample_values = df[col].dropna().astype(str)
                # Check if values look like UK postcodes
                postcode_pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'
                if sample_values.str.match(postcode_pattern, case=False).sum() / len(sample_values) > 0.3:
                    return FileType.PROPERTY_SCHEDULE
        
        # Check for UPRN pattern (12 digits)
        for col in df.columns:
            if 'uprn' in col.lower():
                sample_values = df[col].dropna().astype(str)
                if sample_values.str.match(r'^\d{12}$').sum() / len(sample_values) > 0.5:
                    return FileType.PROPERTY_SCHEDULE
        
        # Default: if it's CSV/Excel and we can't determine, assume property schedule
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.csv', '.xlsx', '.xls']:
            return FileType.PROPERTY_SCHEDULE
        
        return FileType.UNKNOWN
    
    def detect_file_type_from_pdf_content(
        self,
        file_content: bytes,
        filename: str,
    ) -> FileType:
        """
        Detect file type by extracting and analyzing PDF text content.
        
        Args:
            file_content: PDF file content bytes
            filename: File name for context
            
        Returns:
            Detected FileType
        """
        try:
            # Extract text from PDF (first few pages for performance)
            extracted_text = self._extract_pdf_text(file_content, max_pages=5)
            if not extracted_text:
                return FileType.UNKNOWN
            
            text_lower = extracted_text.lower()
            
            # Check for FRAEW keywords (PAS 9980) - most specific, check first
            fraew_score = sum(
                1 for keyword in self.FRAEW_KEYWORDS
                if keyword in text_lower
            )
            if fraew_score >= 2:  # Need multiple keywords for confidence
                return FileType.FRAEW_DOCUMENT
            
            # Check for SCR keywords (Safety Case Report)
            scr_score = sum(
                1 for keyword in self.SCR_KEYWORDS
                if keyword in text_lower
            )
            if scr_score >= 2:
                return FileType.SCR_DOCUMENT
            
            # Check for FRSA keywords (more specific than FRA)
            frsa_score = sum(
                1 for keyword in self.FRSA_KEYWORDS
                if keyword in text_lower
            )
            if frsa_score >= 1:
                return FileType.FRSA_DOCUMENT
            
            # Check for FRA keywords (Fire Risk Assessment)
            fra_score = sum(
                1 for keyword in self.FRA_KEYWORDS
                if keyword in text_lower
            )
            if fra_score >= 1:
                return FileType.FRA_DOCUMENT
            
            # Check for general fire/safety keywords as fallback
            fire_safety_score = sum(
                1 for keyword in self.FIRE_SAFETY_KEYWORDS
                if keyword in text_lower
            )
            if fire_safety_score >= 3:  # Need multiple general keywords
                # Default to FRA if we have fire/safety keywords but can't be more specific
                return FileType.FRA_DOCUMENT
            
            return FileType.UNKNOWN
            
        except Exception:
            # If PDF extraction fails, return UNKNOWN to fall back to filename
            return FileType.UNKNOWN
    
    def _extract_pdf_text(
        self,
        file_content: bytes,
        max_pages: int = 5,
    ) -> Optional[str]:
        """
        Extract text from PDF file content.
        
        Args:
            file_content: PDF file content bytes
            max_pages: Maximum number of pages to extract (for performance)
            
        Returns:
            Extracted text or None if extraction fails
        """
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text_parts = []
                # Extract text from first few pages (usually contains title/header info)
                pages_to_check = min(len(pdf.pages), max_pages)
                for i in range(pages_to_check):
                    page = pdf.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                return "\n".join(text_parts) if text_parts else None
        except Exception:
            return None
    
    def _read_to_dataframe(
        self,
        file_content: bytes,
        extension: str,
    ) -> Optional[pd.DataFrame]:
        """
        Read file content into pandas DataFrame.
        
        Args:
            file_content: File content bytes
            extension: File extension
            
        Returns:
            DataFrame or None if read fails
        """
        try:
            if extension == '.csv':
                return pd.read_csv(io.BytesIO(file_content), nrows=100)  # Read first 100 rows for detection
            elif extension in ['.xlsx', '.xls']:
                return pd.read_excel(io.BytesIO(file_content), nrows=100)
            return None
        except Exception:
            return None
