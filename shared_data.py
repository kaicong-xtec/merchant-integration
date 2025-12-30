"""
Shared data storage for main bot and webhook server
In production, this should be replaced with a proper database
"""

from datetime import datetime
from typing import Dict, Any

# In-memory storage (use database in production)
user_accounts: Dict[int, Dict[str, Any]] = {}
pending_orders: Dict[str, Dict[str, Any]] = {}

def get_user_account(user_id: int) -> dict:
    """Get or create user account"""
    if user_id not in user_accounts:
        user_accounts[user_id] = {
            'balance': 0.0,
            'transactions': [],
            'created_at': datetime.now().isoformat()
        }
    return user_accounts[user_id]

def add_transaction(user_id: int, tx_type: str, amount: float, status: str, order_id: str = "", note: str = ""):
    """Add transaction record"""
    account = get_user_account(user_id)
    transaction = {
        'type': tx_type,
        'amount': amount,
        'status': status,
        'order_id': order_id,
        'note': note,
        'timestamp': datetime.now().isoformat()
    }
    account['transactions'].append(transaction)

def add_pending_order(order_id: str, order_data: dict):
    """Add pending order"""
    pending_orders[order_id] = order_data

def get_pending_order(order_id: str) -> dict:
    """Get pending order"""
    return pending_orders.get(order_id)

def remove_pending_order(order_id: str):
    """Remove pending order"""
    if order_id in pending_orders:
        del pending_orders[order_id]

def update_user_balance(user_id: int, amount: float):
    """Update user balance"""
    account = get_user_account(user_id)
    account['balance'] += amount

def update_transaction_status(user_id: int, order_id: str, status: str):
    """Update transaction status"""
    account = get_user_account(user_id)
    for tx in account['transactions']:
        if tx['order_id'] == order_id:
            tx['status'] = status
            break
