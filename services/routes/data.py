"""
Data purchase routes for Vectra VTU Backend
Handles data plan purchases and queries
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
data_bp = Blueprint('data', __name__, url_prefix='/api/v1/data')

@data_bp.route('/plans/<network>', methods=['GET'])
def get_data_plans(network):
    """
    Get available data plans for a network
    
    Args:
        network: Network name (mtn|glo|airtel|9mobile)
        
    Response:
    {
        "success": true,
        "data": {
            "plans": [...],
            "network": "mtn"
        }
    }
    """
    network = network.lower()
    
    # Validate network
    if network not in ['mtn', 'glo', 'airtel', '9mobile']:
        return jsonify({
            'success': False,
            'message': 'Invalid network. Must be one of: mtn, glo, airtel, 9mobile'
        }), 400
    
    # Map network name to IA Café network ID
    network_id_map = {
        'mtn': 1,
        'glo': 2,
        'airtel': 3,
        '9mobile': 4
    }
    
    network_id = network_id_map[network]
    
    try:
        # Fetch data plans from IA Café
        plans_response = iacafe_service.get_data_plans(network_id)
        
        if plans_response.get('success'):
            return jsonify({
                'success': True,
                'data': {
                    'plans': plans_response.get('data', []),
                    'network': network
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': plans_response.get('message', 'Failed to fetch data plans')
            }), 400
            
    except Exception as e:
        logger.error(f"Error fetching data plans: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch data plans'
        }), 500

@data_bp.route('/purchase', methods=['POST'])
def purchase_data():
    """
    Purchase data plan for a phone number
    
    Request Body:
    {
        "user_id": "optional_user_id",
        "phone": "070XXXXXXXX",
        "network": "mtn|glo|airtel|9mobile",
        "data_plan_id": 5001,
        "amount": 1000,
        "amount_charged": 1000
    }
    
    Response:
    {
        "success": true,
        "message": "Data purchase initiated",
        "data": {
            "request_id": "unique_request_id",
            "transaction": {...}
        }
    }
    """
    data = request.get_json()
    logger.info(f"purchase_data request: phone={data.get('phone')}, network={data.get('network')}, amount={data.get('amount')}")
    
    # Validate required fields
    required_fields = ['phone', 'network', 'data_plan_id', 'amount', 'amount_charged']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    phone = data['phone']
    network = data['network'].lower()
    data_plan_id = int(data['data_plan_id'])
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
    
    # Validate data plan ID
    if data_plan_id <= 0:
        return jsonify({
            'success': False,
            'message': 'Invalid data plan ID'
        }), 400
    
    # Generate unique request ID
    request_id = f"VECTRA_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"
    
    db: Session = next(get_db())

    # DB-first: insert INITIATED transaction
    try:
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

        transaction = Transaction(
            request_id=request_id,
            user_id=user_id,
            service=ServiceType.DATA,
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

    # Transition to PROCESSING
    try:
        transaction = change_transaction_status(db, transaction, TransactionStatus.PROCESSING)
    except Exception as e:
        logger.error(f"Failed to set transaction to PROCESSING: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to process transaction'
        }), 500

    # Call IA Café API
    try:
        api_response = iacafe_service.purchase_data(
            request_id=request_id,
            phone=phone,
            network=network,
            data_plan_id=data_plan_id
        )

        transaction.provider_response = api_response
        transaction.iacafe_reference = api_response.get('reference', '')
        transaction.iacafe_status = api_response.get('status', '')
        db.add(transaction)
        db.commit()

        logger.info(f"IA Café API response for {request_id}: {api_response}")

        if not api_response.get('success'):
            try:
                transaction = change_transaction_status(db, transaction, TransactionStatus.FAILED)
            except Exception:
                logger.exception("Failed to mark transaction FAILED after provider failure")

            return jsonify({
                'success': False,
                'message': f"Data purchase failed: {api_response.get('message', 'Unknown error')}",
                'data': {
                    'request_id': request_id,
                    'transaction': transaction.to_dict(),
                    'api_response': api_response
                }
            }), 400

        return jsonify({
            'success': True,
            'message': 'Data purchase initiated successfully',
            'data': {
                'request_id': request_id,
                'transaction': transaction.to_dict(),
                'api_response': api_response
            }
        }), 200

    except Exception as api_error:
        transaction.provider_response = {'error': str(api_error)}
        transaction.error_message = str(api_error)
        db.add(transaction)
        db.commit()

        try:
            transaction = change_transaction_status(db, transaction, TransactionStatus.FAILED)
        except Exception:
            logger.exception("Failed to mark transaction FAILED after provider exception")

        logger.error(f"IA Café API error for {request_id}: {str(api_error)}")
        logger.critical(f"REFUND REQUIRED: Data transaction {request_id} failed. Amount: {amount_charged}")

        return jsonify({
            'success': False,
            'message': 'Data purchase failed. Please try again.',
            'data': {
                'request_id': request_id,
                'transaction': transaction.to_dict()
            }
        }), 500

@data_bp.route('/status/<request_id>', methods=['GET'])
def get_data_status(request_id):
    """
    Get status of a data purchase
    
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
            Transaction.service == ServiceType.DATA
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