from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    manictime_server_url = fields.Char(
        string='ManicTime Server URL', 
        help='Default ManicTime Server URL',
        config_parameter='manictime_server.server_url'
    )
    
    manictime_auth_type = fields.Selection(
        [
            ('bearer', 'Bearer Token (OAuth)'),
            ('ntlm', 'Windows Authentication (NTLM)'),
        ],
        string='Default Authentication Type',
        help='Default authentication method for ManicTime server',
        config_parameter='manictime_server.auth_type',
        default='bearer'
    )
    
    manictime_sync_interval = fields.Integer(
        string='Sync Interval (days)',
        help='How many days to look back when syncing activities (max 7 days recommended for Odoo.sh deployments)',
        config_parameter='manictime_server.sync_interval',
        default=7
    )