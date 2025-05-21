from odoo import models, fields, api

class ManicTimeEnvironment(models.Model):
    _name = 'manictime.environment'
    _description = 'ManicTime Environment'
    _rec_name = 'device_name'
    _order = 'device_name'
    
    environment_id = fields.Char(
        string='Environment ID',
        required=True,
        help='Unique identifier for this environment'
    )
    device_name = fields.Char(
        string='Device Name',
        required=True,
        help='Name of the device in this environment'
    )
    device_display_name = fields.Char(
        string='Device Display Name',
        help='Display name of the device'
    )
    timeline_ids = fields.One2many(
        'manictime.user.timeline',
        'environment_id',
        string='Timelines',
        help='Timelines from this environment'
    )
    timeline_count = fields.Integer(
        string='Timeline Count',
        compute='_compute_timeline_count',
        help='Number of timelines in this environment'
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        help='User who owns this environment',
        ondelete='cascade'
    )
    
    _sql_constraints = [
        ('environment_id_uniq', 'unique(environment_id)', 'Environment ID must be unique!')
    ]
    
    @api.depends('timeline_ids')
    def _compute_timeline_count(self):
        for env in self:
            env.timeline_count = len(env.timeline_ids)
    
    def name_get(self):
        result = []
        for env in self:
            name = env.device_display_name or env.device_name or env.environment_id
            result.append((env.id, name))
        return result
    
    def action_view_timelines(self):
        """Open the timelines view for this environment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Timelines',
            'res_model': 'manictime.user.timeline',
            'view_mode': 'list,form',
            'domain': [('environment_id', '=', self.id)],
            'context': {'default_environment_id': self.id},
            'path': f'manictime-environment-{self.id}-timelines'
        }