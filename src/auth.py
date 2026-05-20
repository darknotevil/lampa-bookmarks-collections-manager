"""
Authentication module for Lampa MX.

Handles login flows, token management, and session persistence.
"""

import json
from typing import Optional
from .models import Account, Profile
from .utils import (
    load_account,
    save_account,
    clear_account,
    validate_code,
    ACCOUNT_PATH
)


class LampaAuth:
    """
    Authentication handler for Lampa MX.
    
    Provides methods for:
    - QR code login (via 6-digit code)
    - Token-based login
    - Session management
    - Token validation
    
    Usage:
        auth = LampaAuth()
        
        # Login with code from QR scan
        account = auth.login_with_code("123456")
        
        # Or login with existing token
        account = auth.login_with_token("your_token", "profile_id")
        
        # Check if authenticated
        if auth.is_authenticated():
            print(f"Logged in as {auth.account.email}")
    """

    def __init__(self, domain: str = "cub.rip", protocol: str = "https", account_path: Optional[str] = None):
        """
        Initialize authentication handler.
        
        Args:
            domain: CUB domain
            protocol: HTTP protocol
            account_path: Path to save/load account data
        """
        self.domain = domain
        self.protocol = protocol
        self.account_path = account_path or str(ACCOUNT_PATH)
        self.account: Optional[Account] = None
        self._token: Optional[str] = None
        self._profile_id: Optional[str] = None
        
        # Try to load saved session
        self._load_session()

    def _load_session(self) -> None:
        """Load saved account session if exists."""
        saved = load_account(self.account_path)
        if saved and saved.get('token'):
            self.account = Account.from_dict(saved)
            self._token = self.account.token
            self._profile_id = self.account.profile.id if self.account.profile else None

    def _save_session(self) -> None:
        """Save current account session."""
        if self.account:
            save_account(self.account.to_dict(), self.account_path)

    def _get_api_url(self, path: str) -> str:
        """Build API URL."""
        return f"{self.protocol}://{self.domain}/api/{path}"

    def login_with_code(self, code: str) -> Account:
        """
        Login using 6-digit code from QR scan.
        
        Flow:
        1. User scans QR code on cub.rip/add
        2. User enters 6-digit code shown on TV
        3. Code is sent to /api/device/add
        4. Server returns token and account data
        
        Args:
            code: 6-digit numeric code
            
        Returns:
            Account object with token
            
        Raises:
            ValueError: If code is invalid
            RuntimeError: If login fails
        """
        if not validate_code(code):
            raise ValueError(f"Invalid code: '{code}'. Must be 6 digits.")
        
        import requests
        
        url = self._get_api_url('device/add')
        
        try:
            response = requests.post(url, json={'code': code}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Login failed: {e}")
        
        # Create account from response
        self.account = Account(
            token=data['token'],
            email=data.get('email'),
            id=data.get('id'),
        )
        
        # Parse profile if present
        if 'profile' in data and data['profile']:
            self.account.profile = Profile(**data['profile'])
        
        self._token = data['token']
        self._profile_id = self.account.profile.id if self.account.profile else data.get('id')
        
        # Save session
        self._save_session()
        
        return self.account

    def login_with_token(self, token: str, profile_id: Optional[str] = None, email: Optional[str] = None) -> Account:
        """
        Login using existing authentication token.
        
        Useful for:
        - Resuming session from backup
        - Using token extracted from browser
        - Automated testing
        
        Args:
            token: Authentication token
            profile_id: Profile ID (optional)
            email: Email address (optional)
            
        Returns:
            Account object
        """
        self.account = Account(
            token=token,
            email=email,
            id=profile_id,
        )
        
        if profile_id:
            self.account.profile = Profile(id=profile_id)
        
        self._token = token
        self._profile_id = profile_id
        
        # Save session
        self._save_session()
        
        return self.account

    def login_from_dict(self, account_data: dict) -> Account:
        """
        Login using account data dictionary.
        
        Args:
            account_data: Dictionary with token, email, id, profile
            
        Returns:
            Account object
        """
        self.account = Account.from_dict(account_data)
        self._token = self.account.token
        self._profile_id = self.account.profile.id if self.account.profile else self.account.id
        
        self._save_session()
        
        return self.account

    def logout(self) -> None:
        """
        Logout and clear session.
        
        This clears:
        - In-memory account data
        - Saved account file
        - Authentication headers
        """
        self.account = None
        self._token = None
        self._profile_id = None
        clear_account(self.account_path)

    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated.
        
        Returns:
            True if valid token exists
        """
        return self.account is not None and self._token is not None

    def get_token(self) -> Optional[str]:
        """
        Get current authentication token.
        
        Returns:
            Token string or None
        """
        return self._token

    def get_profile_id(self) -> Optional[str]:
        """
        Get current profile ID.
        
        Returns:
            Profile ID or None
        """
        return self._profile_id

    def get_headers(self) -> dict:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dictionary with token and profile headers
            
        Raises:
            RuntimeError: If not authenticated
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call login_with_code() or login_with_token() first.")
        
        headers = {
            'token': self._token,
        }
        
        if self._profile_id:
            headers['profile'] = self._profile_id
        
        return headers

    def validate_token(self) -> bool:
        """
        Validate current token by making a test request.
        
        Returns:
            True if token is valid
        """
        if not self.is_authenticated():
            return False
        
        import requests
        
        try:
            url = self._get_api_url('users/get')
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def refresh_session(self) -> bool:
        """
        Try to refresh the session.
        
        Returns:
            True if session is still valid
        """
        if self.validate_token():
            return True
        
        # Token invalid, clear session
        self.logout()
        return False
