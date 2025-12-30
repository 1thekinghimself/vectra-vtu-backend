"""
Database models for Vectra VTU Backend
Defines the Transaction model with all required fields
Updated for Python 3.13 compatibility
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, Index
from sqlalchemy.sql import func
import enum
from database import Base

class ServiceType(str, enum.Enum):
    """Enum for service types"""
    AIRTIME = 'airtime'
    DATA = 'data'

class TransactionStatus(str, enum.Enum):
    """Enum for transaction statuses"""
    PENDING = 'PENDING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'
    PROCESSING = 'PROCESSING'

class NetworkType(str, enum.Enum):
    """Enum for network types"""
    MTN = 'mtn'
    GLO = 'glo'
    AIRTEL = 'airtel'
    ETISALAT = '9mobile'

class Transaction(Base):
    """Transaction model for storing all VTU transactions"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(String(50), nullable=True, index=True)  # Can be null for anonymous transactions
    service = Column(SQLEnum(ServiceType), nullable=False)
    network = Column(SQLEnum(NetworkType), nullable=False)
    phone = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)  # Amount requested by user
    amount_charged = Column(Float, nullable=False)  # Actual amount charged (may include fees)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    iacafe_reference = Column(String(100), nullable=True)  # IA Café's transaction reference
    iacafe_status = Column(String(50), nullable=True)  # Original IA Café status
    error_message = Column(String(500), nullable=True)  # Store error details if any
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Create composite index for faster queries
    __table_args__ = (
        Index('idx_user_service_status', 'user_id', 'service', 'status'),
        Index('idx_phone_created', 'phone', 'created_at'),
    )
    
    def to_dict(self):
        """Convert transaction to dictionary for API responses"""
        return {
            'id': self.id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'service': self.service.value if self.service else None,
            'network': self.network.value if self.network else None,
            'phone': self.phone,
            'amount': self.amount,
            'amount_charged': self.amount_charged,
            'status': self.status.value if self.status else None,
            'iacafe_reference': self.iacafe_reference,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<Transaction {self.request_id}: {self.service.value if self.service else 'N/A'} - {self.status.value if self.status else 'N/A'}>"