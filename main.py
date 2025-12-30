import asyncio
import logging
import os
import uuid
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

# Import KKPay API class and shared data
from kkpay_api import KKPayAPI
from shared_data import (
    get_user_account, add_transaction, add_pending_order, 
    get_pending_order, remove_pending_order
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot and KKPay configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
KKPAY_MERCHANT_ID = os.getenv('KKPAY_MERCHANT_ID', 'demo_merchant_123')
KKPAY_SECRET = os.getenv('KKPAY_SECRET', 'demo_secret_key_456')
CALLBACK_URL = os.getenv('CALLBACK_URL', 'https://your-domain.com/callback')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# FSM States
class UserStates(StatesGroup):
    waiting_for_topup_amount = State()
    waiting_for_withdraw_amount = State()
    waiting_for_recipient_tg_id = State()

# Initialize KKPay API
kkpay = KKPayAPI(KKPAY_MERCHANT_ID, KKPAY_SECRET)

def get_main_menu_keyboard():
    """Create main menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 充值余额", callback_data="topup"),
            InlineKeyboardButton(text="💸 提现余额", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton(text="👤 我的账户", callback_data="account"),
            InlineKeyboardButton(text="📊 交易记录", callback_data="transactions")
        ],
        [
            InlineKeyboardButton(text="ℹ️ 帮助说明", callback_data="help")
        ]
    ])
    return keyboard

def get_back_keyboard():
    """Create back button keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ 返回主菜单", callback_data="main_menu")]
    ])

def get_coin_selection_keyboard():
    """Create coin selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 CNY (人民币)", callback_data="coin_cny"),
            InlineKeyboardButton(text="💎 USDT", callback_data="coin_usdt")
        ],
        [
            InlineKeyboardButton(text="🔷 TRX", callback_data="coin_trx"),
            InlineKeyboardButton(text="🪙 KKCOIN", callback_data="coin_kkcoin")
        ],
        [
            InlineKeyboardButton(text="⬅️ 返回", callback_data="main_menu")
        ]
    ])
    return keyboard

@dp.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "用户"
    
    # Initialize user account
    account = get_user_account(user_id)
    
    welcome_text = f"""
🏪 **欢迎来到抖音商城钱包系统**

你好 {username}！

这是一个模拟的电商平台钱包，支持通过 KKPay 进行充值和提现。

**当前账户状态:**
• 余额: ¥{account['balance']:.2f}
• 账户状态: 正常
• 支持币种: CNY, USDT, TRX, KKCOIN

请选择要执行的操作:
    """
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Show main menu"""
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name or "用户"
    account = get_user_account(user_id)
    
    welcome_text = f"""
🏪 **抖音商城钱包系统**

你好 {username}！

**当前账户状态:**
• 余额: ¥{account['balance']:.2f}
• 账户状态: 正常
• 支持币种: CNY, USDT, TRX, KKCOIN

请选择要执行的操作:
    """
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "topup")
async def start_topup(callback: CallbackQuery, state: FSMContext):
    """Start top up process"""
    text = """
💰 **充值余额**

请选择充值使用的币种:

• **CNY**: 人民币，支持支付宝/微信支付
• **USDT**: 泰达币，稳定币
• **TRX**: 波场币
• **KKCOIN**: KKPay平台币 (1 USDT = 100,000 KKCOIN)
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_coin_selection_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("coin_"))
async def select_coin_for_topup(callback: CallbackQuery, state: FSMContext):
    """Handle coin selection for topup"""
    coin = callback.data.replace("coin_", "").upper()
    await state.update_data(operation="topup", coin=coin)
    
    coin_names = {
        'CNY': '人民币',
        'USDT': 'USDT',
        'TRX': 'TRX', 
        'KKCOIN': 'KKCOIN'
    }
    
    text = f"""
💰 **充值余额 - {coin_names.get(coin, coin)}**

请输入要充值的金额:

**注意事项:**
• 最低充值金额: 1 {coin}
• 充值会收取少量手续费
• 充值通常在几分钟内到账

请输入充值金额 (仅数字):
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(UserStates.waiting_for_topup_amount)

@dp.message(UserStates.waiting_for_topup_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    """Process top up amount"""
    try:
        amount = float(message.text.strip())
        if amount < 1:
            await message.answer("❌ 最低充值金额为 1")
            return
        
        data = await state.get_data()
        coin = data['coin']
        user_id = message.from_user.id
        
        # Generate unique order ID
        user_order = f"topup_{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Create payment link via KKPay
        username = message.from_user.username or message.from_user.first_name or "用户"
        display_name = f"抖音商城充值 - {username}"
        
        logger.info(f"Creating payment link: user_order={user_order}, amount={amount}, coin={coin}")
        
        # Store pending order
        add_pending_order(user_order, {
            'user_id': user_id,
            'amount': amount,
            'coin': coin,
            'type': 'topup',
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        })
        
        response = await kkpay.create_payment_link(user_order, amount, coin, display_name)
        
        if response.get('code') == 1000:
            data = response.get('data', {})
            pay_url = data.get('pay_url', '')
            txid = data.get('txid', '')
            fee = data.get('fee', '0')
            
            # Update pending order with KKPay txid
            order = get_pending_order(user_order)
            if order:
                order['txid'] = txid
            
            # Add pending transaction record
            add_transaction(user_id, 'topup', amount, 'pending', user_order, f"充值 {coin}")
            
            success_text = f"""
✅ **充值订单创建成功**

**订单信息:**
• 订单号: `{user_order}`
• KKPay订单: `{txid}`
• 充值金额: {amount} {coin}
• 预估手续费: {fee} {coin}

**支付链接:** [点击支付]({pay_url})

支付完成后，余额将自动到账。请勿重复支付！
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 前往支付", url=pay_url)],
                [InlineKeyboardButton(text="⬅️ 返回主菜单", callback_data="main_menu")]
            ])
            
        else:
            # Handle error
            error_msg = response.get('message', '未知错误')
            success_text = f"""
❌ **创建充值订单失败**

错误信息: {error_msg}

请稍后重试或联系客服。
            """
            keyboard = get_back_keyboard()
        
        await message.answer(
            success_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ 请输入有效的数字金额")

@dp.callback_query(F.data == "withdraw")
async def start_withdraw(callback: CallbackQuery, state: FSMContext):
    """Start withdrawal process"""
    user_id = callback.from_user.id
    account = get_user_account(user_id)
    
    if account['balance'] <= 0:
        await callback.message.edit_text(
            "❌ **余额不足**\n\n您的账户余额为 0，无法进行提现。\n请先充值再进行提现操作。",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    text = f"""
💸 **提现余额**

**当前余额:** ¥{account['balance']:.2f}

请选择提现使用的币种:

• **CNY**: 提现到支付宝/微信
• **USDT**: 提现USDT到您的KKPay钱包
• **TRX**: 提现TRX到您的KKPay钱包
• **KKCOIN**: 提现KKCOIN到您的KKPay钱包

**注意:** 提现需要收款人已经启动过 @kkpay 机器人
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_coin_selection_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("coin_"))
async def select_coin_for_withdraw(callback: CallbackQuery, state: FSMContext):
    """Handle coin selection for withdrawal"""
    # Check if this is for withdrawal
    data = await state.get_data()
    if data.get('operation') == 'topup':
        # This is for topup, call the topup handler
        await select_coin_for_topup(callback, state)
        return
    
    coin = callback.data.replace("coin_", "").upper()
    user_id = callback.from_user.id
    account = get_user_account(user_id)
    
    await state.update_data(operation="withdraw", coin=coin)
    
    coin_names = {
        'CNY': '人民币',
        'USDT': 'USDT',
        'TRX': 'TRX',
        'KKCOIN': 'KKCOIN'
    }
    
    text = f"""
💸 **提现余额 - {coin_names.get(coin, coin)}**

**当前余额:** ¥{account['balance']:.2f}

请输入要提现的金额:

**注意事项:**
• 最低提现金额: 1 {coin}
• 提现会收取手续费
• 需要收款人已启动 @kkpay 机器人

请输入提现金额 (仅数字):
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(UserStates.waiting_for_withdraw_amount)

@dp.message(UserStates.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    """Process withdrawal amount"""
    try:
        amount = float(message.text.strip())
        if amount < 1:
            await message.answer("❌ 最低提现金额为 1")
            return
            
        user_id = message.from_user.id
        account = get_user_account(user_id)
        
        if amount > account['balance']:
            await message.answer("❌ 余额不足，请输入不超过余额的金额")
            return
        
        data = await state.get_data()
        coin = data['coin']
        
        await state.update_data(amount=amount)
        
        text = f"""
💸 **提现确认 - {coin}**

**提现金额:** {amount} {coin}
**当前余额:** ¥{account['balance']:.2f}

请输入收款人的 Telegram ID:

**注意:** 收款人必须已经启动过 @kkpay 机器人才能收款

请输入收款人的 Telegram ID:
        """
        
        await message.answer(
            text,
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(UserStates.waiting_for_recipient_tg_id)
        
    except ValueError:
        await message.answer("❌ 请输入有效的数字金额")

@dp.message(UserStates.waiting_for_recipient_tg_id)
async def process_recipient_id(message: Message, state: FSMContext):
    """Process recipient Telegram ID"""
    try:
        recipient_id = int(message.text.strip())
        
        # Check if recipient exists in KKPay system
        check_result = await kkpay.check_user_exists(recipient_id)
        
        if check_result.get('code') != 10000 or not check_result.get('data', {}).get('isExist', False):
            await message.answer(
                "❌ **收款人不存在**\n\n收款人尚未启动 @kkpay 机器人，无法进行转账。\n请让收款人先启动 @kkpay 机器人。",
                parse_mode="Markdown"
            )
            return
        
        data = await state.get_data()
        amount = data['amount']
        coin = data['coin']
        user_id = message.from_user.id
        
        # Generate unique order ID
        user_order = f"withdraw_{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Create withdrawal order via KKPay
        username = message.from_user.username or message.from_user.first_name or "用户"
        display_name = f"抖音商城提现 - {username}"
        
        # Store pending order
        add_pending_order(user_order, {
            'user_id': user_id,
            'recipient_id': recipient_id,
            'amount': amount,
            'coin': coin,
            'type': 'withdraw',
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        })
        
        response = await kkpay.create_withdraw_order(user_order, amount, coin, recipient_id, display_name)
        
        if response.get('code') == 1000:
            data = response.get('data', {})
            txid = data.get('txid', '')
            fee = data.get('fee', '0')
            order_status = data.get('orderStatus', 'pending')
            
            # Update pending order with KKPay txid
            order = get_pending_order(user_order)
            if order:
                order['txid'] = txid
                order['fee'] = fee
            
            # Deduct balance (will be refunded if withdrawal fails)
            account = get_user_account(user_id)
            account['balance'] -= amount
            
            # Add pending transaction record
            add_transaction(user_id, 'withdraw', -amount, 'pending', user_order, f"提现 {coin} 到 {recipient_id}")
            
            success_text = f"""
✅ **提现订单创建成功**

**订单信息:**
• 订单号: `{user_order}`
• KKPay订单: `{txid}`
• 提现金额: {amount} {coin}
• 预估手续费: {fee} {coin}
• 收款人ID: {recipient_id}
• 订单状态: {order_status}

提现正在处理中，完成后会通知您。
剩余余额: ¥{account['balance']:.2f}
            """
            
        else:
            # Handle error
            error_msg = response.get('message', '未知错误')
            success_text = f"""
❌ **创建提现订单失败**

错误信息: {error_msg}

请稍后重试或联系客服。
            """
        
        await message.answer(
            success_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ 请输入有效的 Telegram ID (纯数字)")

@dp.callback_query(F.data == "account")
async def show_account(callback: CallbackQuery):
    """Show account information"""
    user_id = callback.from_user.id
    account = get_user_account(user_id)
    username = callback.from_user.username or callback.from_user.first_name or "用户"
    
    # Calculate transaction statistics
    total_topup = sum(tx['amount'] for tx in account['transactions'] if tx['type'] == 'topup' and tx['status'] == 'success')
    total_withdraw = sum(abs(tx['amount']) for tx in account['transactions'] if tx['type'] == 'withdraw' and tx['status'] == 'success')
    
    text = f"""
👤 **我的账户**

**基本信息:**
• 用户名: {username}
• Telegram ID: {user_id}
• 注册时间: {account['created_at'][:19].replace('T', ' ')}

**账户余额:**
• 当前余额: ¥{account['balance']:.2f}

**交易统计:**
• 总充值: ¥{total_topup:.2f}
• 总提现: ¥{total_withdraw:.2f}
• 交易笔数: {len(account['transactions'])}

**账户状态:** ✅ 正常
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "transactions")
async def show_transactions(callback: CallbackQuery):
    """Show transaction history"""
    user_id = callback.from_user.id
    account = get_user_account(user_id)
    
    if not account['transactions']:
        text = """
📊 **交易记录**

暂无交易记录。

开始充值或提现来查看您的交易历史。
        """
    else:
        text = "📊 **交易记录**\n\n"
        
        # Show last 10 transactions
        recent_transactions = sorted(account['transactions'], key=lambda x: x['timestamp'], reverse=True)[:10]
        
        for tx in recent_transactions:
            tx_type = "充值" if tx['type'] == 'topup' else "提现"
            amount_str = f"+¥{tx['amount']:.2f}" if tx['amount'] > 0 else f"¥{tx['amount']:.2f}"
            status_emoji = "✅" if tx['status'] == 'success' else "⏳" if tx['status'] == 'pending' else "❌"
            
            timestamp = tx['timestamp'][:19].replace('T', ' ')
            
            text += f"""
{status_emoji} **{tx_type}** {amount_str}
• 时间: {timestamp}
• 订单: `{tx['order_id']}`
• 备注: {tx['note']}
            
"""
        
        if len(account['transactions']) > 10:
            text += f"\n... 还有 {len(account['transactions']) - 10} 条记录"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Show help information"""
    text = """
ℹ️ **帮助说明**

**关于本系统:**
这是一个模拟的电商平台钱包系统，集成了 KKPay 支付服务。

**主要功能:**
• 💰 **充值余额**: 通过 KKPay 向账户充值
• 💸 **提现余额**: 从账户提现到 KKPay 钱包
• 👤 **账户管理**: 查看余额和账户信息
• 📊 **交易记录**: 查看充值提现记录

**支持币种:**
• **CNY**: 人民币 (支付宝/微信)
• **USDT**: 泰达币稳定币
• **TRX**: 波场币
• **KKCOIN**: KKPay平台币

**注意事项:**
• 充值和提现都会收取少量手续费
• 提现需要收款人已启动 @kkpay 机器人
• 所有交易都会有记录，可在交易记录中查看

**技术支持:**
如有问题请联系客服或技术支持。

**免责声明:**
本系统仅供测试和演示使用。
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )

@dp.message()
async def handle_unexpected_message(message: Message, state: FSMContext):
    """Handle unexpected messages"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "请使用 /start 命令开始使用抖音商城钱包系统。",
            reply_markup=get_main_menu_keyboard()
        )

# Webhook handler for KKPay callbacks (for production use with a web server)
async def handle_kkpay_callback(callback_data: dict):
    """Handle KKPay payment callbacks"""
    try:
        business_type = callback_data.get('businessType')
        
        if business_type == 'deposit':
            # Handle successful deposit
            user_order = callback_data.get('userOrder')
            amount = float(callback_data.get('amount', 0))
            pay_user = callback_data.get('payUser')
            
            if user_order in pending_orders:
                order = pending_orders[user_order]
                user_id = order['user_id']
                
                # Update account balance
                account = get_user_account(user_id)
                account['balance'] += amount
                
                # Update transaction status
                for tx in account['transactions']:
                    if tx['order_id'] == user_order:
                        tx['status'] = 'success'
                        break
                
                # Clean up pending order
                del pending_orders[user_order]
                
                # Notify user (in production, you'd send a message)
                logger.info(f"Deposit successful: user_id={user_id}, amount={amount}")
                
        elif business_type == 'withdrawalPendingConfirm':
            # Handle withdrawal confirmation request
            user_order = callback_data.get('userOrder')
            # In production, you would implement logic to confirm or reject the withdrawal
            logger.info(f"Withdrawal pending confirmation: {user_order}")
            
        elif business_type == 'withdraw':
            # Handle withdrawal completion
            user_order = callback_data.get('userOrder')
            order_status = callback_data.get('orderStatus')
            
            if user_order in pending_orders:
                order = pending_orders[user_order]
                user_id = order['user_id']
                
                # Update transaction status
                account = get_user_account(user_id)
                for tx in account['transactions']:
                    if tx['order_id'] == user_order:
                        tx['status'] = order_status
                        break
                
                # If withdrawal failed, refund the balance
                if order_status == 'fail':
                    account['balance'] += order['amount']
                
                # Clean up pending order
                del pending_orders[user_order]
                
                logger.info(f"Withdrawal completed: user_id={user_id}, status={order_status}")
                
    except Exception as e:
        logger.error(f"Error handling KKPay callback: {e}")

async def main():
    """Main function to start the bot"""
    logger.info("Starting 抖音商城钱包系统...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
