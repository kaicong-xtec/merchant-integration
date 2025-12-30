"""
KKPay Webhook Server
Handles callbacks from KKPay for payment and withdrawal notifications
"""

import asyncio
import json
import logging
import os
import base64
import hashlib
from datetime import datetime
from aiohttp import web, ClientSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
KKPAY_MERCHANT_ID = os.getenv('KKPAY_MERCHANT_ID', 'demo_merchant_123')
KKPAY_SECRET = os.getenv('KKPAY_SECRET', 'demo_secret_key_456')
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8080'))
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')

# Import shared data functions
from shared_data import (
    get_user_account, add_transaction, get_pending_order, 
    remove_pending_order, update_user_balance, update_transaction_status
)

def verify_signature(data: str, received_signature: str) -> bool:
    """Verify KKPay callback signature"""
    try:
        message = data + KKPAY_SECRET
        hash_obj = hashlib.sha256(message.encode('utf-8')).digest()
        expected_signature = base64.b64encode(hash_obj).decode('utf-8')
        return expected_signature == received_signature
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

async def send_telegram_message(user_id: int, text: str):
    """Send message to user via Telegram Bot API"""
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN not configured, cannot send Telegram message")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': user_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    try:
        async with ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    logger.info(f"Message sent to user {user_id}")
                else:
                    logger.error(f"Failed to send message to user {user_id}: {response.status}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

async def handle_deposit_callback(callback_data: dict):
    """Handle successful deposit callback"""
    user_order = callback_data.get('userOrder')
    amount = float(callback_data.get('amount', 0))
    pay_user = callback_data.get('payUser')
    order_status = callback_data.get('orderStatus', 'success')
    
    logger.info(f"Processing deposit callback: {user_order}, amount: {amount}, status: {order_status}")
    
    order = get_pending_order(user_order)
    if order:
        user_id = order['user_id']
        
        # Update account balance
        account = get_user_account(user_id)
        if order_status == 'success':
            update_user_balance(user_id, amount)
            
            # Update transaction status
            update_transaction_status(user_id, user_order, 'success')
            
            # Send notification to user
            message = f"""
✅ **充值成功通知**

您的充值已到账！
• 充值金额: {amount} {order['coin']}
• 订单号: `{user_order}`
• 当前余额: ¥{account['balance'] + amount:.2f}

感谢您的使用！
            """
            await send_telegram_message(user_id, message)
        
        # Clean up pending order
        remove_pending_order(user_order)
        logger.info(f"Deposit processed successfully: user_id={user_id}, amount={amount}")
    else:
        logger.warning(f"Deposit callback received for unknown order: {user_order}")

async def handle_withdraw_callback(callback_data: dict):
    """Handle withdrawal completion callback"""
    user_order = callback_data.get('userOrder')
    order_status = callback_data.get('orderStatus')
    amount = float(callback_data.get('amount', 0))
    
    logger.info(f"Processing withdraw callback: {user_order}, status: {order_status}")
    
    order = get_pending_order(user_order)
    if order:
        user_id = order['user_id']
        account = get_user_account(user_id)
        
        # Update transaction status
        update_transaction_status(user_id, user_order, order_status)
        
        # If withdrawal failed, refund the balance
        if order_status == 'fail':
            update_user_balance(user_id, order['amount'])
            message = f"""
❌ **提现失败通知**

您的提现订单处理失败，金额已退回账户。
• 提现金额: {order['amount']} {order['coin']}
• 订单号: `{user_order}`
• 当前余额: ¥{account['balance'] + order['amount']:.2f}

如有疑问，请联系客服。
            """
        else:
            message = f"""
✅ **提现成功通知**

您的提现已完成！
• 提现金额: {order['amount']} {order['coin']}
• 收款人: {order['recipient_id']}
• 订单号: `{user_order}`
• 当前余额: ¥{account['balance']:.2f}

感谢您的使用！
            """
        
        await send_telegram_message(user_id, message)
        
        # Clean up pending order
        remove_pending_order(user_order)
        logger.info(f"Withdraw processed: user_id={user_id}, status={order_status}")
    else:
        logger.warning(f"Withdraw callback received for unknown order: {user_order}")

async def handle_withdraw_confirm_callback(callback_data: dict):
    """Handle withdrawal confirmation request callback"""
    user_order = callback_data.get('userOrder')
    amount = float(callback_data.get('amount', 0))
    to_user_id = callback_data.get('toUserId')
    
    logger.info(f"Withdrawal confirmation requested: {user_order}")
    
    # In a real system, you might want to:
    # 1. Send notification to admin for manual review
    # 2. Implement auto-approval logic based on business rules
    # 3. Call KKPay API to confirm or reject the withdrawal
    
    # For demo, we'll just log and auto-approve
    logger.info(f"Auto-approving withdrawal: {user_order} (amount: {amount}, to: {to_user_id})")

async def kkpay_webhook_handler(request):
    """Handle KKPay webhook callbacks"""
    try:
        # Get headers
        merchant_id = request.headers.get('KKPAY-ID')
        signature = request.headers.get('KKPAY-SIGN')
        
        if merchant_id != KKPAY_MERCHANT_ID:
            logger.warning(f"Invalid merchant ID: {merchant_id}")
            return web.json_response(
                {"status": "error", "message": "Invalid merchant ID"}, 
                status=401
            )
        
        # Get request body
        body = await request.text()
        
        # Verify signature
        if not verify_signature(body, signature):
            logger.warning("Invalid signature")
            return web.json_response(
                {"status": "error", "message": "Invalid signature"}, 
                status=401
            )
        
        # Decode and parse data
        try:
            decoded_data = base64.b64decode(body).decode('utf-8')
            callback_data = json.loads(decoded_data)
        except Exception as e:
            logger.error(f"Failed to decode callback data: {e}")
            return web.json_response(
                {"status": "error", "message": "Invalid data format"}, 
                status=400
            )
        
        business_type = callback_data.get('businessType')
        logger.info(f"Received callback: {business_type}")
        
        # Handle different callback types
        if business_type == 'deposit':
            await handle_deposit_callback(callback_data)
        elif business_type == 'withdraw':
            await handle_withdraw_callback(callback_data)
        elif business_type == 'withdrawalPendingConfirm':
            await handle_withdraw_confirm_callback(callback_data)
        else:
            logger.warning(f"Unknown business type: {business_type}")
        
        return web.json_response({"status": "success"})
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return web.json_response(
            {"status": "error", "message": str(e)}, 
            status=500
        )

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({"status": "healthy", "service": "KKPay Webhook Server"})

def create_app():
    """Create and configure the web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_post('/kkpay/callback', kkpay_webhook_handler)
    app.router.add_get('/health', health_check)
    
    return app

async def main():
    """Start the webhook server"""
    app = create_app()
    
    logger.info(f"Starting KKPay Webhook Server on {WEBHOOK_HOST}:{WEBHOOK_PORT}")
    logger.info(f"Webhook URL: http://your-domain.com/kkpay/callback")
    logger.info(f"Health check: http://your-domain.com/health")
    
    # Start the server
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    await site.start()
    
    logger.info("Webhook server started successfully")
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
