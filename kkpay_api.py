import json
import hashlib
import base64
import aiohttp
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# KKPay API endpoints (Corrected based on documentation)
KKPAY_BASE_URL = 'https://www.gamepay.tech/merchant/'
KKPAY_API_BASE_URL = 'https://www.gamepay.tech/api/merchant/'
KKPAY_ENDPOINTS = {
    'payLink': KKPAY_BASE_URL + 'payLink',                    # /merchant/payLink
    'createWithdrawOrder': KKPAY_BASE_URL + 'createWithdrawOrder',  # /merchant/createWithdrawOrder
    'checkDeposit': KKPAY_BASE_URL + 'checkDeposit',          # /merchant/checkDeposit
    'checkWithdraw': KKPAY_API_BASE_URL + 'checkWithdraw',    # /api/merchant/checkWithdraw (has /api/)
    'censorUserByTG': KKPAY_API_BASE_URL + 'censorUserbyTGID'  # /api/merchant/censorUserbyTGID (has /api/)
}

class KKPayAPI:
    """KKPay API integration class"""
    
    def __init__(self, merchant_id: str, secret: str):
        self.merchant_id = merchant_id
        self.secret = secret
    
    def generate_sign(self, data: str) -> str:
        """Generate signature for KKPay API"""
        message = data + self.secret
        hash_obj = hashlib.sha256(message.encode('utf-8')).digest()
        signature = base64.b64encode(hash_obj).decode('utf-8')
        return signature
    
    async def make_request(self, endpoint: str, data: dict) -> dict:
        """Make API request to KKPay"""
        try:
            # Encode data
            json_data = json.dumps(data)
            base64_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
            
            # Generate signature
            sign = self.generate_sign(base64_data)
            
            # Headers
            headers = {
                'Content-Type': 'application/json',
                'KKPAY-SIGN': sign,
                'KKPAY-ID': self.merchant_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, data=base64_data, headers=headers) as response:
                    response_text = await response.text()
                    
                    # Parse response
                    try:
                        response_data = json.loads(response_text)
                        return response_data
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response: {response_text}")
                        return {'code': 9999, 'message': 'Invalid response format'}
                        
        except Exception as e:
            logger.error(f"KKPay API request failed: {e}")
            return {'code': 9999, 'message': str(e)}
    
    async def create_payment_link(self, user_order: str, amount: float, coin: str, name: str = "") -> dict:
        """Create payment link for top up"""
        data = {
            'userOrder': user_order,
            'amount': amount,
            'coin': coin,
            'name': name,
            'return_url': 'https://t.me/TimiSupport_bot'  # Return to bot after payment
        }
        return await self.make_request(KKPAY_ENDPOINTS['payLink'], data)
    
    async def create_withdraw_order(self, user_order: str, amount: float, coin: str, to_user_id: int, name: str = "") -> dict:
        """Create withdrawal order"""
        data = {
            'userOrder': user_order,
            'amount': amount,
            'coin': coin,
            'to_user_id': to_user_id,
            'name': name
        }
        return await self.make_request(KKPAY_ENDPOINTS['createWithdrawOrder'], data)
    
    async def check_user_exists(self, tg_id: int) -> dict:
        """Check if user exists in KKPay system"""
        data = {'tg_id': str(tg_id)}
        return await self.make_request(KKPAY_ENDPOINTS['censorUserByTG'], data)
    
    async def check_deposit_order(self, txid: str) -> dict:
        """Check deposit order status"""
        data = {'txid': txid}
        return await self.make_request(KKPAY_ENDPOINTS['checkDeposit'], data)
    
    async def check_withdraw_order(self, txid: str) -> dict:
        """Check withdraw order status"""
        data = {'txid': txid}
        return await self.make_request(KKPAY_ENDPOINTS['checkWithdraw'], data)
