"""
Database models for Vectra VTU Backend.

This file defines the `Transaction` model and required enums.
"""
from datetime import datetime
import enum
import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    Enum as SQLEnum,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import validates

from database import Base


class ServiceType(str, enum.Enum):
    airtime = 'airtime'
    data = 'data'


class TransactionStatus(str, enum.Enum):
    INITIATED = 'INITIATED'
    PROCESSING = 'PROCESSING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'


class Transaction(Base):
    """Transaction model for storing VTU transactions.

    Fields (mandatory):
    - id: UUID string (primary key)
    - request_id: unique request identifier (DB-level unique + index)
    - user_id: nullable, for guest/anonymous
    - service_type: ENUM('airtime','data')
    - network: provider network name
    - phone: destination phone number
    - amount: numeric amount requested
    - status: ENUM (validated at model level)
    - provider_reference: nullable provider reference string
    - provider_response: nullable JSON payload from provider
    - created_at, updated_at: timestamps
    """

    __tablename__ = 'transactions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    service_type = Column(SQLEnum(ServiceType, validate_strings=True), nullable=False)
    network = Column(String(50), nullable=False)
    phone = Column(String(32), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(SQLEnum(TransactionStatus, validate_strings=True), nullable=False)
    provider_reference = Column(String(200), nullable=True)
    provider_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('request_id', name='uq_transactions_request_id'),
        Index('ix_transactions_user_service_status', 'user_id', 'service_type', 'status'),
    )

    @validates('status')
    def validate_status(self, key, value):
        """Ensure status is a valid TransactionStatus value."""
        if value is None:
            raise ValueError('status cannot be None')
        if isinstance(value, TransactionStatus):
            return value
        try:
            return TransactionStatus(value)
        except ValueError:
            raise ValueError(f'Invalid status: {value}. Must be one of {[s.value for s in TransactionStatus]}')

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'service_type': self.service_type.value if self.service_type else None,
            'network': self.network,
            'phone': self.phone,
            'amount': self.amount,
            'status': self.status.value if self.status else None,
            'provider_reference': self.provider_reference,
            'provider_response': self.provider_response,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Transaction {self.request_id} {self.service_type.value} {self.status.value}>"