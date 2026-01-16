"""
GDPR compliance configuration.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


# TODO Placeholder - TBD the needed scope 
class ConsentType(Enum):
    """Types of GDPR consents."""
    DATA_PROCESSING = "data_processing"
    DATA_SHARING = "data_sharing"
    MARKETING = "marketing"


class DeletionType(Enum):
    """Types of data deletion."""
    GDPR_REQUEST = "gdpr_request"
    RETENTION_POLICY = "retention_policy"
    MANUAL = "manual"


@dataclass
class RetentionPolicy:
    """Data retention policy configuration."""
    data_type: str  # 'property_data', 'upload_files', 'audit_logs'
    retention_days: int
    auto_delete: bool = True


class GDPRConfig:
    """GDPR compliance configuration."""
    
    def __init__(self):
        """Initialize GDPR configuration."""
        self.default_retention_policies = {
            'property_data': RetentionPolicy('property_data', retention_days=2555, auto_delete=True),  # 7 years
            'upload_files': RetentionPolicy('upload_files', retention_days=2555, auto_delete=True),  # 7 years
            'audit_logs': RetentionPolicy('audit_logs', retention_days=2555, auto_delete=True),  # 7 years
            'pii_mappings': RetentionPolicy('pii_mappings', retention_days=2555, auto_delete=True),  # 7 years
        }
    
    def get_retention_policy(self, data_type: str) -> Optional[RetentionPolicy]:
        """
        Get retention policy for a data type.
        
        Args:
            data_type: Type of data
            
        Returns:
            RetentionPolicy or None
        """
        return self.default_retention_policies.get(data_type)
    
    def set_retention_policy(self, data_type: str, retention_days: int, auto_delete: bool = True):
        """
        Set retention policy for a data type.
        
        Args:
            data_type: Type of data
            retention_days: Number of days to retain
            auto_delete: Whether to auto-delete after retention period
        """
        self.default_retention_policies[data_type] = RetentionPolicy(
            data_type=data_type,
            retention_days=retention_days,
            auto_delete=auto_delete,
        )


# Global GDPR config instance
_gdpr_config: Optional[GDPRConfig] = None


def get_gdpr_config() -> GDPRConfig:
    """Get global GDPR config instance (singleton)."""
    global _gdpr_config
    if _gdpr_config is None:
        _gdpr_config = GDPRConfig()
    return _gdpr_config
