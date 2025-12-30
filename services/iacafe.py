"""
IA Café API Service Wrapper
Handles all communication with IA Café VTU API
Updated for PythonAnywhere compatibility
"""
import requests
import uuid
import logging
import os
import sys
import json
from typing import Dict, Any, Optional
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)

class IACafeService:
    """Service for interacting with IA Café VTU API"""
    
    def __init__(self):
        """Initialize IA Café service with API credentials"""
        self.base_url = config.IACAFE_BASE_URL
        self.api_key = config.IACAFE_API_KEY
        
        print(f"🔧 Initializing IA Café Service...")
        print(f"   Base URL: {self.base_url}")
        print(f"   API Key present: {'Yes' if self.api_key else 'No'}")
        if self.api_key:
            print(f"   API Key (first 10 chars): {self.api_key[:10]}...")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'VectraVTU/1.0'
        }
        
        # Network ID mapping for IA Café
        self.network_id_map = {
            'mtn': 1,
            'glo': 2,
            'airtel': 3,
            '9mobile': 4
        }
        
        # Service ID mapping for IA Café
        self.service_id_map = {
            'mtn': 'mtn',
            'glo': 'glo',
            'airtel': 'airtel',
            '9mobile': '9mobile'
        }
        
        # Configure proxies for PythonAnywhere
        self.proxies = self._configure_proxies()
        
        print(f"   PythonAnywhere detected: {'Yes' if 'pythonanywhere' in os.environ.get('HOME', '') else 'No'}")
        print(f"   Proxies configured: {bool(self.proxies)}")
        print(f"✅ IA Café Service initialized")
    
    def _configure_proxies(self) -> Dict:
        """
        Configure proxies for PythonAnywhere environment
        PythonAnywhere free tier blocks most outbound HTTPS connections
        """
        proxies = {}
        
        # Check if we're on PythonAnywhere
        if 'pythonanywhere' in os.environ.get('HOME', ''):
            print("   🐍 PythonAnywhere environment detected")
            
            # Try different proxy configurations
            proxy_options = [
                'http://proxy.server:3128',  # Common PythonAnywhere proxy
                None,  # No proxy (sometimes works for whitelisted domains)
            ]
            
            # Test which proxy works
            for proxy_url in proxy_options:
                if proxy_url:
                    proxies = {
                        'http': proxy_url,
                        'https': proxy_url,
                    }
                    print(f"   🔄 Trying proxy: {proxy_url}")
                    
                    # Test connection
                    test_url = 'https://www.pythonanywhere.com'
                    try:
                        test_response = requests.get(test_url, proxies=proxies, timeout=5)
                        if test_response.status_code == 200:
                            print(f"   ✅ Proxy {proxy_url} works!")
                            return proxies
                    except:
                        continue
            
            print("   ⚠️ No working proxy found, trying without proxy")
        
        return {}
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """
        Make HTTP request to IA Café API with error handling
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: Request payload
            
        Returns:
            Dict containing response data
            
        Raises:
            Exception: If API request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        print(f"\n🌐 Making {method} request to IA Café API")
        print(f"   URL: {url}")
        print(f"   Endpoint: {endpoint}")
        if data:
            print(f"   Payload: {json.dumps(data, indent=2)}")
        
        try:
            logger.info(f"Making {method} request to {endpoint}")
            
            request_kwargs = {
                'headers': self.headers,
                'timeout': 30,
                'proxies': self.proxies
            }
            
            if method.upper() == 'GET':
                if data:
                    request_kwargs['params'] = data
                response = requests.get(url, **request_kwargs)
            else:  # POST
                if data:
                    request_kwargs['json'] = data
                response = requests.post(url, **request_kwargs)
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                # Provide the response body for diagnostics (without leaking secrets)
                status = response.status_code
                text = response.text
                logger.error(f"IA Café HTTP error {status}: {text}")
                raise Exception(f"IA Café API request failed: {status} {text}")

            result = response.json()
            print(f"✅ API Response: {json.dumps(result, indent=2)}")
            logger.info(f"API Response: {result}")

            return result
            
        except requests.exceptions.ConnectTimeout as e:
            error_msg = f"Connection timeout to IA Café API: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise Exception(error_msg)
            
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL error with IA Café API: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            # Try without SSL verification as last resort
            print("🔄 Retrying without SSL verification...")
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=self.headers, params=data, timeout=30, verify=False)
                else:
                    response = requests.post(url, headers=self.headers, json=data, timeout=30, verify=False)
                
                result = response.json()
                print(f"✅ API Response (no SSL): {json.dumps(result, indent=2)}")
                return result
            except Exception as retry_error:
                raise Exception(f"IA Café API request failed even without SSL: {str(retry_error)}")
            
        except requests.exceptions.ProxyError as e:
            error_msg = f"Proxy error: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            print("🔄 Retrying without proxy...")
            # Try without proxy
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=self.headers, params=data, timeout=30)
                else:
                    response = requests.post(url, headers=self.headers, json=data, timeout=30)
                
                result = response.json()
                print(f"✅ API Response (no proxy): {json.dumps(result, indent=2)}")
                return result
            except Exception as retry_error:
                raise Exception(f"IA Café API request failed: {str(retry_error)}")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API Request failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            
            # Diagnostic information
            print("\n🔍 Diagnostic Information:")
            print(f"   Python Version: {sys.version}")
            print(f"   Requests Version: {requests.__version__}")
            print(f"   Platform: {sys.platform}")
            print(f"   PythonAnywhere: {'pythonanywhere' in os.environ.get('HOME', '')}")
            
            raise Exception(f"IA Café API request failed: {str(e)}")
    
    def purchase_airtime(self, request_id: str, phone: str, network: str, amount: float) -> Dict[str, Any]:
        """
        Purchase airtime via IA Café API
        
        Args:
            request_id: Unique request ID
            phone: Recipient phone number
            network: Network provider
            amount: Amount to purchase
            
        Returns:
            Dict containing API response
        """
        print(f"\n🛒 Purchasing Airtime")
        print(f"   Request ID: {request_id}")
        print(f"   Phone: {phone}")
        print(f"   Network: {network}")
        print(f"   Amount: ₦{amount}")
        
        # Validate network
        if network not in self.service_id_map:
            error_msg = f"Invalid network: {network}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        payload = {
            "request_id": request_id,
            "phone": phone,
            "service_id": self.service_id_map[network],
            "amount": amount
        }
        
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = self._make_request('POST', '/airtime', payload)
            return response
        except Exception as e:
            error_msg = f"Airtime purchase failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise
    
    def get_data_plans(self, network_id: int) -> Dict[str, Any]:
        """
        Get available data plans for a network
        
        Args:
            network_id: Network ID (1-4)
            
        Returns:
            Dict containing data plans
        """
        print(f"\n📊 Fetching Data Plans")
        print(f"   Network ID: {network_id}")
        
        if not 1 <= network_id <= 4:
            error_msg = f"Network ID must be between 1 and 4, got {network_id}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            response = self._make_request('GET', f'/budget-data/plans?network_id={network_id}')
            
            if response.get('success'):
                plans = response.get('data', [])
                print(f"✅ Found {len(plans)} data plans")
                for plan in plans[:5]:  # Show first 5 plans
                    print(f"   - {plan.get('name')}: ₦{plan.get('price')}")
                if len(plans) > 5:
                    print(f"   ... and {len(plans) - 5} more")
            else:
                print(f"⚠️ API returned success=False: {response.get('message')}")
            
            return response
        except Exception as e:
            error_msg = f"Failed to fetch data plans: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise
    
    def purchase_data(self, request_id: str, phone: str, network: str, data_plan_id: int) -> Dict[str, Any]:
        """
        Purchase data plan via IA Café API
        
        Args:
            request_id: Unique request ID
            phone: Recipient phone number
            network: Network provider
            data_plan_id: Data plan ID from IA Café
            
        Returns:
            Dict containing API response
        """
        print(f"\n🛒 Purchasing Data Plan")
        print(f"   Request ID: {request_id}")
        print(f"   Phone: {phone}")
        print(f"   Network: {network}")
        print(f"   Data Plan ID: {data_plan_id}")
        
        # Validate network
        if network not in self.network_id_map:
            error_msg = f"Invalid network: {network}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        payload = {
            "request_id": request_id,
            "phone": phone,
            "data_plan": data_plan_id,
            "network_id": self.network_id_map[network]
        }
        
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = self._make_request('POST', '/budget-data', payload)
            return response
        except Exception as e:
            error_msg = f"Data purchase failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise
    
    def get_order_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check order status from IA Café
        
        Args:
            request_id: Original request ID
            
        Returns:
            Dict containing order status
        """
        print(f"\n📋 Checking Order Status")
        print(f"   Request ID: {request_id}")
        
        try:
            response = self._make_request('GET', f'/orders/{request_id}')
            return response
        except Exception as e:
            error_msg = f"Failed to get order status: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise
    
    def requery_order(self, request_id: str) -> Dict[str, Any]:
        """
        Requery an order from IA Café
        
        Args:
            request_id: Original request ID
            
        Returns:
            Dict containing requery response
        """
        print(f"\n🔄 Requerying Order")
        print(f"   Request ID: {request_id}")
        
        payload = {"request_id": request_id}
        
        try:
            response = self._make_request('POST', '/requery', payload)
            return response
        except Exception as e:
            error_msg = f"Requery failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            raise
    
    def normalize_status(self, iacafe_status: str) -> str:
        """
        Normalize IA Café status to internal status
        
        Args:
            iacafe_status: Status from IA Café
            
        Returns:
            Normalized status string
        """
        status_map = {
            'processing-api': 'PENDING',
            'completed-api': 'SUCCESS',
            'refunded': 'REFUNDED',
            'unprocessable': 'FAILED',
            '422': 'FAILED'
        }
        
        normalized = status_map.get(iacafe_status, 'PENDING')
        print(f"📊 Status Normalization: '{iacafe_status}' → '{normalized}'")
        return normalized
    
    def test_connection(self) -> bool:
        """
        Test connection to IA Café API
        
        Returns:
            bool: True if connection successful
        """
        print(f"\n🔌 Testing IA Café API Connection")
        print(f"   URL: {self.base_url}")
        
        try:
            # Try to get data plans for MTN (network_id=1)
            response = self.get_data_plans(1)
            success = response.get('success', False)
            print(f"   Connection test: {'✅ SUCCESS' if success else '❌ FAILED'}")
            if not success:
                print(f"   Error: {response.get('message', 'Unknown error')}")
            return success
        except Exception as e:
            print(f"❌ Connection test failed: {str(e)}")
            return False

# Create singleton instance
iacafe_service = IACafeService()

# Test connection on import (for debugging)
if __name__ == "__main__":
    print("\n" + "="*50)
    print("IA Café Service - Direct Test")
    print("="*50)
    
    service = IACafeService()
    
    # Test connection
    if service.test_connection():
        print("\n✅ IA Café API is accessible!")
    else:
        print("\n❌ Cannot connect to IA Café API")
        print("\n💡 Troubleshooting steps:")
        print("1. Check if IA Café domain is whitelisted on PythonAnywhere")
        print("2. Verify API key is correct")
        print("3. Check PythonAnywhere network restrictions")
        print("4. Consider upgrading to paid account for API access")