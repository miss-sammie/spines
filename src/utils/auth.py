"""
Access Control for Spines 2.0
Handles Tailscale vs public access, read-only controls
"""
from functools import wraps
from flask import request, jsonify, current_app
from utils.logging import get_logger

logger = get_logger(__name__)

class AccessControl:
    def __init__(self, app):
        self.app = app
        
    @property
    def config(self):
        return current_app.config['SPINES_CONFIG']
    
    def is_tailscale_request(self, request):
        """Check if request comes from Tailscale network"""
        # Tailscale IPs are in 100.64.0.0/10 range
        remote_ip = request.remote_addr
        
        # Check for Tailscale IP range
        if remote_ip and remote_ip.startswith('100.'):
            return True
            
        # Check port-based detection (8888 = v1 Tailscale, 8890 = v2 Tailscale, 8889 = public)
        if request.host and (':8888' in request.host or ':8890' in request.host):
            return True
            
        # Local development
        if remote_ip in ['127.0.0.1', 'localhost', '::1']:
            return True
            
        return False
    
    def is_public_request(self, request):
        """Check if request comes from public web"""
        return not self.is_tailscale_request(request)
    
    def is_admin_user(self, user_id=None):
        """Check if user is an admin (for future auth integration)"""
        if not user_id:
            return False
        return user_id in self.config.ADMIN_USERS
    
    def check_access(self, operation='read'):
        """Decorator to check access permissions"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                
                # For write operations, check if public read-only mode
                if operation == 'write':
                    if self.is_public_request(request) and self.config.PUBLIC_READ_ONLY:
                        logger.warning(f"Write operation blocked for public request: {request.remote_addr}")
                        return jsonify({
                            'error': 'Read-only access',
                            'message': 'Public access is read-only. Use Tailscale for full access.'
                        }), 403
                
                # Log access for monitoring
                access_type = 'tailscale' if self.is_tailscale_request(request) else 'public'
                logger.info(f"{operation} operation from {access_type}: {request.remote_addr}")
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def filter_for_public(self, data):
        """Filter sensitive data for public access"""
        if self.is_tailscale_request(request):
            return data
        
        # Remove sensitive fields for public access
        if isinstance(data, dict):
            return self._filter_dict(data)
        elif isinstance(data, list):
            return [self._filter_dict(item) if isinstance(item, dict) else item for item in data]
        
        return data
    
    def _filter_dict(self, data):
        """Filter sensitive fields from dictionary"""
        sensitive_fields = [
            'contributor', 'date_added', 'file_path', 'extraction_confidence',
            'folder_name', 'path', 'migrated_from_v1', 'migration_date'
        ]
        
        return {k: v for k, v in data.items() if k not in sensitive_fields}

# Decorator for requiring write access
def require_write_access(f):
    """Decorator to require write access for an endpoint"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_control = current_app.access_control
        
        if access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
            logger.warning(f"Write operation blocked for public request: {request.remote_addr}")
            return jsonify({
                'error': 'Read-only access',
                'message': 'Public access is read-only. Use Tailscale for full access.'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function 