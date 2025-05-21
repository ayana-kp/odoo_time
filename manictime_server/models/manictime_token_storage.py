from odoo import models, api
import base64
import logging
import uuid
import hashlib

_logger = logging.getLogger(__name__)

# Try to import keyring but don't fail if not available
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

class ManicTimeTokenStorage(models.AbstractModel):
    _name = 'manictime.token.storage'
    _description = 'ManicTime Token Storage'
    
    @api.model
    def get_param_name(self, user_id, key_type):
        """Generate parameter name for storing secrets"""
        # Create a unique identifier for this user and key type
        user_hash = hashlib.sha256(f"{user_id}_{key_type}".encode()).hexdigest()[:16]
        return f"manictime_secret.{user_hash}"
    
    @api.model
    def store_secret(self, user_id, secret, key_type='client_secret'):
        """Store a secret securely for a user
        
        Args:
            user_id: The ID of the user
            secret: The secret to store
            key_type: Type of key (client_secret, access_token, refresh_token, etc.)
        
        Returns:
            bool: Success or failure
        """
        if not secret:
            return False
            
        param_name = self.get_param_name(user_id, key_type)
        
        # Encode secret
        encoded_secret = base64.b64encode(secret.encode('utf-8')).decode('utf-8')
        
        # Store in system parameters (encrypted in database)
        self.env['ir.config_parameter'].sudo().set_param(param_name, encoded_secret)
        
        # Also try to store in keyring if available (more secure)
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password("odoo_manictime", f"{user_id}_{key_type}", secret)
            except Exception as e:
                _logger.warning(f"Could not store in keyring: {str(e)}. Using parameters only.")
                
        return True
    
    @api.model
    def get_secret(self, user_id, key_type='client_secret'):
        """Retrieve a stored secret for a user
        
        Args:
            user_id: The ID of the user
            key_type: Type of key (client_secret, access_token, refresh_token, etc.)
            
        Returns:
            str: The secret, or None if not found
        """
        # Try keyring first if available
        if KEYRING_AVAILABLE:
            try:
                secret = keyring.get_password("odoo_manictime", f"{user_id}_{key_type}")
                if secret:
                    return secret
            except Exception as e:
                _logger.warning(f"Could not retrieve from keyring: {str(e)}")
                
        # Fall back to system parameters
        param_name = self.get_param_name(user_id, key_type)
        encoded_secret = self.env['ir.config_parameter'].sudo().get_param(param_name)
        
        if encoded_secret:
            try:
                return base64.b64decode(encoded_secret.encode('utf-8')).decode('utf-8')
            except Exception as e:
                _logger.error(f"Failed to decode secret: {str(e)}")
                
        return None
    
    @api.model
    def delete_secret(self, user_id, key_type='client_secret'):
        """Delete a stored secret for a user
        
        Args:
            user_id: The ID of the user
            key_type: Type of key (client_secret, access_token, refresh_token, etc.)
            
        Returns:
            bool: Success or failure
        """
        # Delete from system parameters
        param_name = self.get_param_name(user_id, key_type)
        self.env['ir.config_parameter'].sudo().set_param(param_name, False)
        
        # Also try to delete from keyring if available
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password("odoo_manictime", f"{user_id}_{key_type}")
            except Exception:
                pass  # Ignore keyring errors on deletion
                
        return True