from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    manictime_exact_tag_matching = fields.Boolean(
        string='Use Exact Tag Matching',
        help='When enabled, the system will directly match ManicTime tags to project codes '
             'without requiring explicit mappings. For example, if your project code is "048", '
             'it will match ManicTime activities tagged with "048" without needing a mapping record.',
        config_parameter='manictime_timesheet.exact_tag_matching'
    )