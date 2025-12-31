"""
Airtime purchase routes for Vectra VTU Backend
Handles airtime purchase requests and responses
"""
from flask import Blueprint, request, jsonify
import uuid
import logging
from datetime import datetime

from models import Transaction, TransactionStatus, ServiceType, NetworkType
from services.iacafe import iacafe_service
from services.transaction_service import change_transaction_status
from database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Create blueprint
airtime_bp = Blueprint('airtime', __name__, url_prefix='/api/v1/airtime')

@airtime_bp.route('/purchase', methods=['POST'])
def purchase_airtime():
    """
    Purchase airtime for a phone number
    
    Request Body:
    {
        "user_id": "optional_user_id",
        "phone": "070XXXXXXXX",
        "network": "mtn|glo|airtel|9mobile",
        "amount": 100,
        "amount_charged": 100
    }
    
    Response:
    {
        "success": true,
        "message": "Airtime purchase initiated",
        "data": {
            "request_id": "unique_request_id",
            "transaction": {...}
        }
    }
    """
    data = request.get_json()
    logger.info(f"purchase_airtime request: phone={data.get('phone')}, network={data.get('network')}, amount={data.get('amount')}")
    
    # Validate required fields
    required_fields = ['phone', 'network', 'amount', 'amount_charged']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    phone = data['phone']
    network = data['network'].lower()
    amount = float(data['amount'])
    amount_charged = float(data['amount_charged'])
    user_id = data.get('user_id')
    
    # Validate network
    if network not in ['mtn', 'glo', 'airtel', '9mobile']:
        return jsonify({
            'success': False,
            'message': 'Invalid network. Must be one of: mtn, glo, airtel, 9mobile'
        }), 400
    
    # Validate amount
    if amount <= 0 or amount_charged <= 0:
        return jsonify({
            'success': False,
            'message': 'Amount must be greater than 0'
        }), 400
    
    # Generate unique request ID
    request_id = f"VECTRA_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"
    
    db: Session = next(get_db())

    # DB-first: ensure we insert transaction with INITIATED status before calling provider
    try:
        # Check for duplicate request (idempotency)
        existing_transaction = db.query(Transaction).filter(
            Transaction.request_id == request_id
        ).first()

        if existing_transaction:
            return jsonify({
                'success': False,
                'message': 'Duplicate request detected',
                'data': {
                    'request_id': request_id,
                    'transaction': existing_transaction.to_dict()
                }
            }), 409

        # Create transaction record with INITIATED status (DB-first)
        transaction = Transaction(
            request_id=request_id,
            user_id=user_id,
            service=ServiceType.AIRTIME,
            network=NetworkType(network),
            phone=phone,
            amount=amount,
            amount_charged=amount_charged,
            status=TransactionStatus.INITIATED
        )

        db.add(transaction)
        db.commit()

        logger.info(f"Created transaction INITIATED: {request_id} for {phone}")

    except Exception as e:
        db.rollback()
        logger.error(f"Transaction creation failed (abort, no provider call): {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to create transaction'
        }), 500

    # Move to PROCESSING before calling provider
    try:
        transaction = change_transaction_status(db, transaction, TransactionStatus.PROCESSING)
    except Exception as e:
        logger.error(f"Failed to set transaction to PROCESSING: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to process transaction'
        }), 500

    # Call IA Café API (sync for MVP)
    try:
        api_response = iacafe_service.purchase_airtime(
            request_id=request_id,
            phone=phone,
            network=network,
            amount=amount
        )

        # Store full provider response
        transaction.provider_response = api_response
        transaction.iacafe_reference = api_response.get('reference', '')
        transaction.iacafe_status = api_response.get('status', '')
        db.add(transaction)
        db.commit()

        logger.info(f"IA Café API response for {request_id}: {api_response}")

        # If provider reports failure immediately, mark FAILED; otherwise keep PROCESSING
        if not api_response.get('success'):
            try:
                transaction = change_transaction_status(db, transaction, TransactionStatus.FAILED)
            except Exception:
                # log and continue returning failure
                logger.exception("Failed to mark transaction FAILED after provider failure")

            return jsonify({
                'success': False,
                'message': f"Airtime purchase failed: {api_response.get('message', 'Unknown error')}",
                'data': {
                    'request_id': request_id,
                    'transaction': transaction.to_dict(),
                    'api_response': api_response
                }
            }), 400

        # Success path: don't mark SUCCESS here; webhook will confirm
        return jsonify({
            'success': True,
            'message': 'Airtime purchase initiated successfully',
            'data': {
                'request_id': request_id,
                'transaction': transaction.to_dict(),
                'api_response': api_response
            }
        }), 200

    except Exception as api_error:
        # Provider call failed — store error and mark FAILED
        transaction.provider_response = {'error': str(api_error)}
        transaction.error_message = str(api_error)
        db.add(transaction)
        db.commit()

        try:
            transaction = change_transaction_status(db, transaction, TransactionStatus.FAILED)
        except Exception:
            logger.exception("Failed to mark transaction FAILED after provider exception")

        logger.error(f"IA Café API error for {request_id}: {str(api_error)}")
        logger.critical(f"REFUND REQUIRED: Transaction {request_id} failed. Amount: {amount_charged}")

        return jsonify({
            'success': False,
            'message': 'Airtime purchase failed. Please try again.',
            'data': {
                'request_id': request_id,
                'transaction': transaction.to_dict()
            }
        }), 500

@airtime_bp.route('/status/<request_id>', methods=['GET'])
def get_airtime_status(request_id):
    """
    Get status of an airtime purchase
    
    Args:
        request_id: Transaction request ID
        
    Response:
    {
        "success": true,
        "data": {
            "transaction": {...}
        }
    }
    """
    db: Session = next(get_db())
    
    try:
        transaction = db.query(Transaction).filter(
            Transaction.request_id == request_id,
            Transaction.service == ServiceType.AIRTIME
        ).first()
        
        if not transaction:
            return jsonify({
                'success': False,
                'message': 'Transaction not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'transaction': transaction.to_dict()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching transaction status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500