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
from sqlalchemy import event
from sqlalchemy.orm.attributes import NO_VALUE


class ServiceType(str, enum.Enum):
    AIRTIME = 'airtime'
    DATA = 'data'


class TransactionStatus(str, enum.Enum):
    INITIATED = 'INITIATED'
    PENDING = 'INITIATED'
    PROCESSING = 'PROCESSING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'


class NetworkType(str, enum.Enum):
    MTN = 'mtn'
    GLO = 'glo'
    AIRTEL = 'airtel'
    ETISALAT = '9mobile'


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
    service = Column(SQLEnum(ServiceType, validate_strings=True), nullable=False)
    network = Column(SQLEnum(NetworkType, validate_strings=True), nullable=False)
    phone = Column(String(32), nullable=False)
    amount = Column(Float, nullable=False)
    amount_charged = Column(Float, nullable=False)
    status = Column(SQLEnum(TransactionStatus, validate_strings=True), nullable=False)
    iacafe_reference = Column(String(100), nullable=True)
    iacafe_status = Column(String(50), nullable=True)
    error_message = Column(String(500), nullable=True)
    provider_reference = Column(String(200), nullable=True)
    provider_response = Column(JSON, nullable=True)
    webhook_payload = Column(JSON, nullable=True)
    webhook_received_at = Column(DateTime(timezone=True), nullable=True)
    webhook_delivery_id = Column(String(200), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('request_id', name='uq_transactions_request_id'),
        Index('ix_transactions_user_service_status', 'user_id', 'service', 'status'),
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
            'service': self.service.value if self.service else None,
            'network': self.network,
            'phone': self.phone,
            'amount': self.amount,
            'status': self.status.value if self.status else None,
            'amount_charged': self.amount_charged,
            'iacafe_reference': self.iacafe_reference,
            'iacafe_status': self.iacafe_status,
            'error_message': self.error_message,
            'provider_reference': self.provider_reference,
            'provider_response': self.provider_response,
            'webhook_delivery_id': self.webhook_delivery_id,
            'webhook_payload': self.webhook_payload,
            'webhook_received_at': self.webhook_received_at.isoformat() if self.webhook_received_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Transaction {self.request_id} {self.service_type.value} {self.status.value}>"


# Allowed lifecycle transitions
_ALLOWED_STATUS_TRANSITIONS = {
    TransactionStatus.INITIATED.value: {TransactionStatus.PROCESSING.value},
    TransactionStatus.PROCESSING.value: {TransactionStatus.SUCCESS.value, TransactionStatus.FAILED.value},
    TransactionStatus.SUCCESS.value: {TransactionStatus.REFUNDED.value},
    TransactionStatus.FAILED.value: set(),
    TransactionStatus.REFUNDED.value: set(),
}


@event.listens_for(Transaction.status, 'set', retval=True)
def _validate_status_transition(target, value, oldvalue, initiator):
    """Reject invalid status transitions globally.

    This listener ensures that any change to `status` follows the
    state machine defined in `_ALLOWED_STATUS_TRANSITIONS`.

    - Initial assignment (oldvalue == NO_VALUE) is allowed only when
      setting `INITIATED`.
    - Re-assigning the same value is a no-op.
    - Any invalid transition raises ValueError.
    """
    # Normalize incoming values to strings
    new = value.value if isinstance(value, TransactionStatus) else value

    # Validate new is a known status
    if new not in {s.value for s in TransactionStatus}:
        raise ValueError(f"Invalid status value: {new}")

    # Allow initial set only to INITIATED
    if oldvalue is NO_VALUE:
        if new != TransactionStatus.INITIATED.value:
            raise ValueError("Initial status must be 'INITIATED'")
        return value

    # No-op if unchanged
    old = oldvalue.value if isinstance(oldvalue, TransactionStatus) else oldvalue
    if old == new:
        return value

    allowed = _ALLOWED_STATUS_TRANSITIONS.get(old)
    if allowed is None:
        raise ValueError(f"Unknown current status: {old}")

    if new not in allowed:
        raise ValueError(f"Invalid status transition: {old} -> {new}")

    return value