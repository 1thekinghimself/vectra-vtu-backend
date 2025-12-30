from sqlalchemy.orm import Session
from models import Transaction, TransactionStatus


def change_transaction_status(db: Session, transaction: Transaction, new_status: str) -> Transaction:
    """Change `transaction.status` to `new_status` enforcing allowed transitions.

    - `new_status` can be a `TransactionStatus` or a string matching one.
    - This function commits the change and returns the refreshed transaction.
    - Any invalid transition will raise a ValueError (enforced at model level).
    """
    # Normalize and validate
    if isinstance(new_status, TransactionStatus):
        status_val = new_status
    else:
        try:
            status_val = TransactionStatus(new_status)
        except Exception:
            raise ValueError(f"Unknown status: {new_status}")

    transaction.status = status_val
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
