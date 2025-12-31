from flask import Blueprint, jsonify, request, current_app
from database import get_db
from sqlalchemy.orm import Session
from services.iacafe import iacafe_service
from services.transaction_service import change_transaction_status
from models import Transaction, TransactionStatus
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

REQUERY_TIMEOUT_MINUTES = 10


@transactions_bp.route('/requery/<request_id>', methods=['GET'])
def requery_transaction(request_id):
    db: Session = next(get_db())
    try:
        transaction = db.query(Transaction).filter(Transaction.request_id == request_id).first()
        if not transaction:
            logger.warning(f"requery: transaction not found: {request_id}")
            return jsonify({'success': False, 'message': 'Transaction not found'}), 404

        logger.info(f"requery: request_id={request_id}, current_status={transaction.status}, time={datetime.utcnow().isoformat()}")

        if transaction.status in (TransactionStatus.SUCCESS, TransactionStatus.FAILED, TransactionStatus.REFUNDED):
            return jsonify({'success': True, 'status': transaction.status.value, 'transaction': transaction.to_dict()}), 200

        # Call provider requery
        try:
            provider_resp = iacafe_service.requery_order(request_id)
        except Exception as e:
            logger.error(f"requery: provider error for {request_id}: {str(e)}")
            return jsonify({'success': False, 'message': 'Provider requery failed', 'error': str(e)}), 502

        # Store provider response
        transaction.provider_response = provider_resp
        transaction.iacafe_status = provider_resp.get('status', transaction.iacafe_status)
        db.add(transaction)
        db.commit()

        # Normalize status and apply safe transition if needed
        normalized = iacafe_service.normalize_status(provider_resp.get('status', ''))
        try:
            if normalized == 'SUCCESS':
                change_transaction_status(db, transaction, TransactionStatus.SUCCESS)
            elif normalized == 'FAILED':
                change_transaction_status(db, transaction, TransactionStatus.FAILED)
            # else leave as PROCESSING/INITIATED
        except Exception as e:
            logger.error(f"requery: invalid transition for {request_id}: {str(e)}")

        logger.info(f"requery: completed for {request_id}, provider_status={provider_resp.get('status')}")
        return jsonify({'success': True, 'transaction': transaction.to_dict(), 'provider_response': provider_resp}), 200

    except Exception as e:
        logger.exception(f"requery: unexpected error for {request_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@transactions_bp.route('/refund/<request_id>', methods=['POST'])
def refund_transaction(request_id):
    db: Session = next(get_db())
    payload = request.get_json() or {}
    reason = payload.get('reason', 'manual refund')
    refund_ref = None

    try:
        transaction = db.query(Transaction).filter(Transaction.request_id == request_id).first()
        if not transaction:
            logger.warning(f"refund: transaction not found: {request_id}")
            return jsonify({'success': False, 'message': 'Transaction not found'}), 404

        now = datetime.utcnow()
        # Allow refund only when FAILED or stuck in PROCESSING beyond timeout
        can_refund = False
        if transaction.status == TransactionStatus.FAILED:
            can_refund = True
        elif transaction.status == TransactionStatus.PROCESSING:
            # determine age from webhook_received_at or updated_at
            updated_at = transaction.updated_at or transaction.created_at
            if updated_at and (now - updated_at) > timedelta(minutes=REQUERY_TIMEOUT_MINUTES):
                can_refund = True

        if not can_refund:
            logger.warning(f"refund: not allowed for {request_id}, status={transaction.status}")
            return jsonify({'success': False, 'message': 'Refund not allowed for current status'}), 400

        # Perform refund logic (placeholder) — in real world call payment gateway or ledger
        # For now, set REFUNDED and store refund reference
        try:
            # if external refund API exists, call here and set refund_ref
            change_transaction_status(db, transaction, TransactionStatus.REFUNDED)
            refund_ref = f"REF_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{request_id[-6:]}"
            transaction.provider_response = transaction.provider_response or {}
            transaction.provider_response['refund_reference'] = refund_ref
            db.add(transaction)
            db.commit()

            logger.info(f"refund: transaction {request_id} refunded, refund_ref={refund_ref}, reason={reason}")
            return jsonify({'success': True, 'refund_reference': refund_ref, 'transaction': transaction.to_dict()}), 200

        except Exception as e:
            db.rollback()
            logger.exception(f"refund: failed for {request_id}: {str(e)}")
            return jsonify({'success': False, 'message': 'Refund failed'}), 500

    except Exception as e:
        logger.exception(f"refund: unexpected error for {request_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
