from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ManicTimeConfig(models.Model):
    _name = 'manictime.config'
    _description = 'ManicTime User Configuration'
    _rec_name = 'user_id'
    
    user_id = fields.Many2one(
        'res.users', 
        string='User', 
        required=True, 
        help='User this configuration belongs to'
    )
    
    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Auto-fill client_id_username with user's email when user is changed"""
        if self.user_id and self.user_id.email:
            self.client_id_username = self.user_id.email
    # Integration is enabled simply by having a configuration record
    # No separate enabled field is needed
    auth_type = fields.Selection(
        [
            ('bearer', 'Bearer Token (OAuth)'),
            ('ntlm', 'Windows Authentication (NTLM)'),
        ],
        string='Authentication Type',
        help='Authentication method for ManicTime server'
    )
    client_id_username = fields.Char(
        string='Client ID / Username',
        help='Client ID for OAuth authentication or Username for NTLM authentication'
    )
    temp_secret = fields.Char(
        string='Client Secret / Password',
        help='Temporary field for authentication - not stored in database'
    )
    token_expiry = fields.Datetime(
        string='Token Expiry',
        help='When the current access token expires',
        readonly=True
    )
    last_sync = fields.Datetime(
        string='Last Sync',
        help='Last time ManicTime data was synchronized',
        readonly=True
    )
    auto_reauth = fields.Boolean(
        string='Auto Reauthenticate',
        default=True,
        help='Automatically attempt to refresh authentication when it expires'
    )
    sync_by_default = fields.Boolean(
        string='Sync Timelines by Default',
        default=True,
        help='When new timelines are discovered, automatically mark them for synchronization'
    )
    
    _sql_constraints = [
        ('user_uniq', 'unique(user_id)', 'A user can only have one ManicTime configuration!')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default values and sync with user record"""
        configs_to_create = []
        result = self.env['manictime.config']
        
        for vals in vals_list:
            # Check if user already has a config
            if vals.get('user_id'):
                existing = self.search([('user_id', '=', vals['user_id'])], limit=1)
                if existing:
                    # Instead of error, update the existing configuration
                    _logger.info(f"User {vals['user_id']} already has a configuration, updating it")
                    existing.write(vals)
                    result += existing
                    continue
                
                # Get defaults from system parameters if not provided
                if not vals.get('auth_type'):
                    vals['auth_type'] = self.env['ir.config_parameter'].sudo().get_param(
                        'manictime_server.auth_type', default='bearer')
                
                # Automatically prefill the Client ID/Username with the user's email
                if not vals.get('client_id_username'):
                    user = self.env['res.users'].browse(vals['user_id'])
                    if user.exists() and user.email:
                        vals['client_id_username'] = user.email
            
            configs_to_create.append(vals)
        
        # Only create configs that don't exist yet
        if configs_to_create:
            new_configs = super(ManicTimeConfig, self).create(configs_to_create)
            result += new_configs
            
            # Apply default sync setting to existing timelines
            for config in new_configs:
                if config.sync_by_default:
                    timelines = self.env['manictime.user.timeline'].search([
                        ('user_id', '=', config.user_id.id),
                        ('is_selected', '=', False)
                    ])
                    if timelines:
                        timelines.write({'is_selected': True})
        
        return result
    
    def write(self, vals):
        """Override write to sync with user record"""
        result = super(ManicTimeConfig, self).write(vals)
        
        # Note: We no longer need to sync with the user record as the user model
        # now uses computed fields that reference this model directly
        
        # If default sync setting changed and is now True, update existing timelines
        for config in self:
            # Apply default sync setting to existing timelines
            if ('sync_by_default' in vals and vals['sync_by_default']) or \
               (hasattr(config, 'sync_by_default') and config.sync_by_default):
                timelines = self.env['manictime.user.timeline'].search([
                    ('user_id', '=', config.user_id.id),
                    ('is_selected', '=', False)
                ])
                if timelines:
                    timelines.write({'is_selected': True})
                    
        return result
    
    def unlink(self):
        """Override unlink to handle user record"""
        # Note: We don't need to update the user record explicitly anymore since
        # the user model uses computed fields that reference this model directly.
        # When this config is deleted, the computed fields will automatically reflect that.
        
        # However, we should clean up any related secure storage
        for config in self:
            # Use the token storage service to delete any saved secrets
            self.env['manictime.token.storage'].sudo().delete_secret(config.user_id.id, 'client_secret')
            self.env['manictime.token.storage'].sudo().delete_secret(config.user_id.id, 'access_token')
            self.env['manictime.token.storage'].sudo().delete_secret(config.user_id.id, 'refresh_token')
            
        return super(ManicTimeConfig, self).unlink()
    
    def name_get(self):
        """Custom name display"""
        result = []
        for config in self:
            result.append((config.id, f"{config.user_id.name}'s ManicTime Config"))
        return result
    
    def action_authenticate(self):
        """Trigger authentication for the user"""
        self.ensure_one()
        
        # Copy temp_secret to user record if provided
        if self.temp_secret:
            secret_length = len(self.temp_secret)
            self.user_id.write({'manictime_temp_secret': self.temp_secret})
            
            # Replace with zeros of the same length to give visual feedback
            # that a password is set without storing the actual value
            zeros = '0' * min(secret_length, 10)  # Use at most 10 zeros
            
            # Clear temp_secret from config by replacing with zeros
            self.write({'temp_secret': zeros})
            
        # Call authenticate method on user
        return self.user_id.manictime_authenticate()
    
    def action_revoke_auth(self):
        """Revoke authentication for the user"""
        self.ensure_one()
        return self.user_id.manictime_revoke_auth()
    
    def action_sync_data(self):
        """Sync data for the user"""
        self.ensure_one()
        return self.user_id.manictime_sync_data()
    
    @api.model
    def cron_check_auth_status(self):
        """Cron job to check authentication status and refresh if needed"""
        configs = self.search([
            ('auto_reauth', '=', True),
            ('token_expiry', '!=', False)
        ])
        
        for config in configs:
            # Check if token is expired or will expire within a day
            if fields.Datetime.now() > config.token_expiry or \
               (config.token_expiry - fields.Datetime.now()).total_seconds() < 86400:  # Less than 1 day
                try:
                    _logger.info(f"Auto-refreshing authentication for user {config.user_id.name}")
                    # Call authenticate as user to refresh token
                    config.user_id.with_user(config.user_id).manictime_authenticate()
                except Exception as e:
                    _logger.error(f"Failed to auto-refresh auth for user {config.user_id.name}: {str(e)}")
                    
        return True