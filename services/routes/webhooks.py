"""
Webhook handlers for Vectra VTU Backend
Handles IA Café webhook notifications with HMAC verification
"""
from flask import Blueprint, request, jsonify, current_app
import hmac
import hashlib
import json
import logging
from datetime import datetime

from models import Transaction, TransactionStatus
from services.transaction_service import change_transaction_status
from database import get_db
from sqlalchemy.orm import Session
from services.iacafe import iacafe_service

logger = logging.getLogger(__name__)

# Create blueprint
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

def verify_webhook_signature(timestamp: str, signature: str, raw_body: bytes, secret: str) -> bool:
    """
    Verify IA Café webhook signature using HMAC-SHA256
    
    Args:
        timestamp: X-VTU-Timestamp header
        signature: X-VTU-Signature header
        raw_body: Raw request body
        secret: Webhook secret
        
    Returns:
        bool: True if signature is valid
    """
    try:
        # Create expected signature
        message = timestamp.encode() + b"." + raw_body
        expected_signature = hmac.new(
            secret.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison for security)
        return hmac.compare_digest(expected_signature, signature)
        
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False

@webhooks_bp.route('/iacafe', methods=['POST'])
def handle_iacafe_webhook():
    """
    Handle IA Café webhook notifications
    
    Webhook Headers:
    - X-VTU-Signature: HMAC-SHA256 signature
    - X-VTU-Timestamp: Timestamp
    - X-VTU-Event: Event type
    - X-VTU-Delivery: Delivery ID
    
    Webhook Body:
    {
        "event": "transaction.status_changed",
        "data": {
            "request_id": "original_request_id",
            "status": "completed-api",
            "reference": "iacafe_ref",
            "amount": 100,
            "phone": "070XXXXXXXX",
            "network": "mtn",
            "service": "airtime",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    }
    
    Response:
    - 200: Webhook processed successfully
    - 401: Invalid signature
    - 400: Invalid webhook data
    - 500: Server error
    """
    # Get webhook headers
    signature = request.headers.get('X-VTU-Signature')
    timestamp = request.headers.get('X-VTU-Timestamp')
    event = request.headers.get('X-VTU-Event')
    delivery_id = request.headers.get('X-VTU-Delivery')
    
    logger.info(f"Received webhook: event={event}, delivery={delivery_id}")
    
    # Validate required headers
    if not all([signature, timestamp, event, delivery_id]):
        logger.warning(f"Missing webhook headers: sig={signature}, ts={timestamp}, event={event}")
        return jsonify({'error': 'Missing required headers'}), 400
    
    # Get raw body for signature verification
    raw_body = request.get_data()
    
    # Get webhook secret from config. If present, verify signature; otherwise skip signature validation.
    secret = current_app.config.get('IACAFE_WEBHOOK_SECRET')
    if secret:
        if not all([signature, timestamp]):
            logger.warning("Missing signature/timestamp headers for signed webhook")
            return jsonify({'error': 'Missing signature headers'}), 400

        if not verify_webhook_signature(timestamp, signature, raw_body, secret):
            logger.warning(f"Invalid webhook signature: delivery={delivery_id}")
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        logger.warning("Webhook secret not configured; skipping signature verification")
    
    # Parse webhook payload
    try:
        payload = request.get_json()
        logger.info(f"Webhook payload: {json.dumps(payload)}")
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {str(e)}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Validate webhook payload
    if not payload or 'event' not in payload or 'data' not in payload:
        logger.warning(f"Invalid webhook payload structure: {payload}")
        return jsonify({'error': 'Invalid webhook payload'}), 400
    
    # Check if event is supported
    supported_events = ['transaction.created', 'transaction.status_changed']
    if payload['event'] not in supported_events:
        logger.info(f"Ignoring unsupported event: {payload['event']}")
        return jsonify({'success': True, 'message': 'Event not supported'}), 200
    
    # Process webhook based on event type
    try:
        data = payload['data']
        request_id = data.get('request_id')
        
        if not request_id:
            logger.warning("Webhook missing request_id")
            return jsonify({'error': 'Missing request_id'}), 400
        
        db: Session = next(get_db())

        # Find transaction by request_id
        transaction = db.query(Transaction).filter(
            Transaction.request_id == request_id
        ).first()

        if not transaction:
            logger.warning(f"Transaction not found for request_id: {request_id} — ignoring webhook")
            return jsonify({'success': True, 'message': 'Transaction not found; ignored'}), 200

        # Idempotency: if we've already processed this delivery, ignore
        if delivery_id and transaction.webhook_delivery_id == delivery_id:
            logger.info(f"Duplicate webhook delivery {delivery_id} for {request_id}; ignoring")
            return jsonify({'success': True, 'message': 'Duplicate delivery ignored'}), 200

        # If transaction already in terminal state, ignore
        if transaction.status in (TransactionStatus.SUCCESS, TransactionStatus.FAILED):
            logger.info(f"Transaction {request_id} already terminal ({transaction.status}); ignoring webhook")
            return jsonify({'success': True, 'message': 'Already terminal; ignored'}), 200
        
        # Update transaction based on webhook data
        iacafe_status = data.get('status')
        reference = data.get('reference')
        
        if iacafe_status:
            transaction.iacafe_status = iacafe_status

            # Normalize IA Café status to internal status
            normalized_status = iacafe_service.normalize_status(iacafe_status)

            # Use safe status transitions via the service
            try:
                if normalized_status == 'SUCCESS':
                    change_transaction_status(db, transaction, TransactionStatus.SUCCESS)
                    logger.info(f"Transaction {request_id} marked as SUCCESS via webhook")

                elif normalized_status == 'REFUNDED':
                    change_transaction_status(db, transaction, TransactionStatus.REFUNDED)
                    logger.info(f"Transaction {request_id} marked as REFUNDED via webhook")
                    logger.critical(f"REFUND PROCESS REQUIRED: Transaction {request_id} was refunded by IA Café")

                elif normalized_status == 'FAILED':
                    change_transaction_status(db, transaction, TransactionStatus.FAILED)
                    logger.info(f"Transaction {request_id} marked as FAILED via webhook")
                    logger.critical(f"REFUND PROCESS REQUIRED: Transaction {request_id} failed. Amount: {transaction.amount_charged}")
            except Exception as e:
                logger.error(f"Invalid webhook status transition for {request_id}: {str(e)}")
                # Do not raise; webhook should be idempotent and resilient
        
        # Store webhook payload and metadata
        transaction.webhook_payload = payload
        transaction.webhook_received_at = datetime.utcnow()
        if delivery_id:
            transaction.webhook_delivery_id = delivery_id

        if reference:
            transaction.iacafe_reference = reference

        # Update any additional data
        transaction.error_message = data.get('error_message', transaction.error_message)

        db.add(transaction)
        db.commit()

        logger.info(f"Webhook processed successfully: request_id={request_id}, status={normalized_status if 'normalized_status' in locals() else 'N/A'}")

        return jsonify({
            'success': True,
            'message': 'Webhook processed',
            'delivery_id': delivery_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.route('/test', methods=['POST'])
def test_webhook():
    """
    Test endpoint for webhook verification (development only)
    
    Note: This should be disabled in production
    """
    return jsonify({
        'success': True,
        'message': 'Webhook test endpoint',
        'headers': dict(request.headers),
        'body': request.get_json()
    }), 200
