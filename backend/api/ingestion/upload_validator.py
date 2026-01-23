"""
File type and size validation for uploads.
"""
import os
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status


class UploadValidator:
    """Validates file uploads."""
    
    # Allowed file types and their extensions
    ALLOWED_TYPES = {
        'property_schedule': ['.csv', '.xlsx', '.xls'],
        'epc_data': ['.csv', '.xlsx', '.xls'],
        'fra_document': ['.pdf'],  # Fire Risk Assessment (includes FRSA)
        'fraew_document': ['.pdf'],  # PAS 9980 - Fire Risk Appraisal of External Walls
        'scr_document': ['.pdf'],  # Safety Case Report
    }

    # Maximum file sizes (in bytes)
    # PDF documents can be large due to scanned pages, images, and detailed reports.
    # Processing is asynchronous via Step Functions, so larger files don't block the API.
    MAX_FILE_SIZES = {
        'property_schedule': 50 * 1024 * 1024,  # 50 MB
        'epc_data': 50 * 1024 * 1024,  # 50 MB
        'fra_document': 50 * 1024 * 1024,  # 50 MB (increased from 10 MB for scanned/image-heavy PDFs)
        'fraew_document': 50 * 1024 * 1024,  # 50 MB (increased from 10 MB for scanned/image-heavy PDFs)
        'scr_document': 50 * 1024 * 1024,  # 50 MB (increased from 10 MB for scanned/image-heavy PDFs)
    }
    
    def validate_file(
        self,
        file: UploadFile,
        file_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file.
        
        Args:
            file: FastAPI UploadFile
            file_type: Expected file type
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file type is allowed
        if file_type not in self.ALLOWED_TYPES:
            return False, f"Invalid file type: {file_type}"
        
        # Check file extension
        filename = file.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_TYPES[file_type]:
            return False, f"Invalid file extension for {file_type}. Allowed: {', '.join(self.ALLOWED_TYPES[file_type])}"
        
        # Check file size
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)  # Reset file pointer
        
        max_size = self.MAX_FILE_SIZES.get(file_type)
        if max_size and file_size > max_size:
            return False, f"File size exceeds maximum allowed size of {max_size / (1024*1024):.1f} MB"
        
        return True, None
    
    def validate_and_raise(self, file: UploadFile, file_type: str):
        """
        Validate file and raise HTTPException if invalid.
        
        Args:
            file: FastAPI UploadFile
            file_type: Expected file type
            
        Raises:
            HTTPException: If validation fails
        """
        is_valid, error_message = self.validate_file(file, file_type)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
