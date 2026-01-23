"""GDPR compliance and data protection."""
from backend.core.gdpr.gdpr_config import (
    GDPRConfig,
    ConsentType,
    DeletionType,
    RetentionPolicy,
    get_gdpr_config,
)
from backend.core.gdpr.data_retention import DataRetentionManager
from backend.core.gdpr.right_to_deletion import RightToDeletion
from backend.core.gdpr.data_export import DataExport
from backend.core.gdpr.consent_manager import ConsentManager

__all__ = [
    'GDPRConfig',
    'ConsentType',
    'DeletionType',
    'RetentionPolicy',
    'get_gdpr_config',
    'DataRetentionManager',
    'RightToDeletion',
    'DataExport',
    'ConsentManager',
]
