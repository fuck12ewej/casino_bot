import aiohttp
import hashlib
import hmac
import json
from typing import Optional, Dict
import logging


class CryptoPayment:
    def __init__(self, api_token: str, testnet: bool = False):
        self.api_token = api_token
        self.testnet = testnet
        
        # Выбор URL в зависимости от режима
        if testnet:
            self.base_url = "https://testnet-pay.crypt.bot/api"
        else:
            self.base_url = "https://pay.crypt.bot/api"
        
        self.headers = {
            "Crypto-Pay-API-Token": api_token
        }
    
    async def create_invoice(self, amount: float, currency: str = "USD", 
                            description: str = "Пополнение баланса казино",
                            user_id: int = None) -> Optional[Dict]:
        """
        Создает инвойс для оплаты согласно Crypto Pay API
        
        Args:
            amount: Сумма
            currency: Валюта (USD, EUR, RUB, etc)
            description: Описание платежа
            user_id: ID пользователя для payload
            
        Returns:
            Dict с информацией об инвойсе или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Согласно документации API
                payload = {
                    "currency_type": "fiat",
                    "fiat": currency,
                    "amount": str(amount),
                    "description": description,
                    "accepted_assets": "USDT,TON,BTC,ETH,TRX,USDC"
                }
                
                if user_id:
                    payload["payload"] = str(user_id)
                
                async with session.post(
                    f"{self.base_url}/createInvoice",
                    headers=self.headers,
                    json=payload
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                            
                            if data.get("ok"):
                                result = data.get("result")
                                logging.info(f"Invoice created: {result.get('invoice_id', 'unknown')}")
                                return result
                            else:
                                error_info = data.get("error", {})
                                error_name = error_info.get("name", "Unknown error")
                                error_code = error_info.get("code", "UNKNOWN")
                                logging.error(f"API error creating invoice: {error_name} ({error_code})")
                                return None
                        except json.JSONDecodeError:
                            logging.error(f"Invalid JSON response: {response_text}")
                            return None
                    else:
                        logging.error(f"Failed to create invoice: HTTP {response.status}, {response_text}")
                        return None
                    
        except Exception as e:
            logging.error(f"Error creating invoice: {e}")
            return None
    
    async def check_invoice(self, invoice_id: int) -> Optional[Dict]:
        """
        Проверяет статус инвойса согласно Crypto Pay API
        
        Args:
            invoice_id: ID инвойса
            
        Returns:
            Dict с информацией об инвойсе или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/getInvoices",
                    headers=self.headers,
                    params={"invoice_ids": str(invoice_id)}
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                            
                            if data.get("ok"):
                                result = data.get("result", {})
                                items = result.get("items", [])
                                
                                if items and len(items) > 0:
                                    invoice = items[0]
                                    logging.info(f"Invoice {invoice_id} status: {invoice.get('status', 'unknown')}")
                                    return invoice
                                else:
                                    logging.debug(f"Invoice {invoice_id} not found in response")
                                    return None
                            else:
                                error_code = data.get("error", {}).get("code", "UNKNOWN")
                                error_name = data.get("error", {}).get("name", "Unknown error")
                                logging.warning(f"API error for invoice {invoice_id}: {error_name} ({error_code})")
                                return None
                        except json.JSONDecodeError:
                            logging.error(f"Invalid JSON response for invoice {invoice_id}: {response_text}")
                            return None
                    else:
                        logging.error(f"Failed to check invoice {invoice_id}: HTTP {response.status}, {response_text}")
                        return None
                        
        except Exception as e:
            logging.error(f"Error checking invoice {invoice_id}: {e}", exc_info=True)
            return None
    
    async def get_balance(self) -> Optional[Dict]:
        """Получает баланс кошелька"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/getBalance",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            return data.get("result")
                    return None
        except Exception as e:
            logging.error(f"Error getting balance: {e}")
            return None
    
    def verify_webhook(self, body: str, signature: str) -> bool:
        """
        Проверяет подпись webhook
        
        Args:
            body: Тело запроса
            signature: Подпись из заголовка
            
        Returns:
            True если подпись валидна
        """
        secret = hashlib.sha256(self.api_token.encode()).digest()
        check_string = body.encode()
        hmac_string = hmac.new(secret, check_string, hashlib.sha256).hexdigest()
        return hmac_string == signature



