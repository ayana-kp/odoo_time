from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ManicTimeActivity(models.Model):
    _name = 'manictime.activity'
    _description = 'ManicTime Activity'
    _order = 'start_time desc'
    _auto = True  # Still create the table in the database

    name = fields.Char(string='Name', required=True, 
                      help='Activity title from ManicTime')
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade',
                            help='User who owns this activity')
    timeline_id = fields.Many2one('manictime.user.timeline', string='Timeline', required=True,
                                 help='Timeline this activity belongs to')
    entity_id = fields.Char(string='Entity ID', 
                            help='Entity ID from ManicTime server')
    start_time = fields.Datetime(string='Start Time', 
                               help='When the activity started')
    end_time = fields.Datetime(string='End Time', 
                             help='When the activity ended')
    duration = fields.Float(string='Duration (hours)', compute='_compute_duration', store=True,
                          help='Duration of the activity in hours')
    tags = fields.Char(string='Tags', 
                     help='Comma-separated list of tags applied to this activity')
    tags_list = fields.Many2many('manictime.tag.combination', string='Tag Combinations',
                               compute='_compute_tags_list', store=False,
                               help='Tag combinations that match this activity')
    application = fields.Char(string='Application', 
                            help='Application used during this activity')
    notes = fields.Text(string='Notes', 
                       help='Additional notes for this activity')

    _sql_constraints = [
        ('user_timeline_entity_uniq', 'unique(user_id, timeline_id, entity_id)', 
         'Activity must be unique per user and timeline!')
    ]

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Calculate duration in hours between start and end times"""
        for activity in self:
            if activity.start_time and activity.end_time:
                duration = (activity.end_time - activity.start_time).total_seconds() / 3600
                activity.duration = round(duration, 2)
            else:
                activity.duration = 0.0
    
    @api.depends('tags', 'user_id')
    def _compute_tags_list(self):
        """Find tag combinations that match this activity's tags"""
        for activity in self:
            if not activity.tags:
                activity.tags_list = False
                continue
                
            activity_tags = set([tag.strip() for tag in activity.tags.split(',') if tag.strip()])
            if not activity_tags:
                activity.tags_list = False
                continue
                
            # Find all tag combinations for this user
            combinations = self.env['manictime.tag.combination'].search([
                ('user_id', '=', activity.user_id.id)
            ])
            
            matching_combinations = []
            for combo in combinations:
                if not combo.tags:
                    continue
                    
                combo_tags = set([tag.strip() for tag in combo.tags.split(',') if tag.strip()])
                # Check if all tags in the combination are in the activity tags
                if combo_tags and combo_tags.issubset(activity_tags):
                    matching_combinations.append(combo.id)
                    
            activity.tags_list = matching_combinations if matching_combinations else False
                
    def name_get(self):
        """Custom name display including duration"""
        result = []
        for activity in self:
            duration_str = f"{activity.duration:.2f}h" 
            result.append((activity.id, f"{activity.name} ({duration_str})"))
        return result
        
    @api.model_create_multi
    def create(self, vals_list):
        """Prevent manual creation of records"""
        # Allow creation only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("ManicTime activities cannot be created manually. They are synchronized automatically from ManicTime server."))
        return super(ManicTimeActivity, self).create(vals_list)
        
    def write(self, vals):
        """Prevent manual updates to records"""
        # Allow updates only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("ManicTime activities cannot be modified manually. They are synchronized automatically from ManicTime server."))
        return super(ManicTimeActivity, self).write(vals)
        
    def unlink(self):
        """Prevent manual deletion of records"""
        # Allow deletion only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("ManicTime activities cannot be deleted manually. They are managed automatically through synchronization."))
        return super(ManicTimeActivity, self).unlink()