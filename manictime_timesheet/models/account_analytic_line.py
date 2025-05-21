from odoo import models, fields, api, _
from odoo.tools import float_round
from datetime import datetime, timedelta
import pytz

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    
    manictime_hours = fields.Float(
        string='ManicTime Hours',
        compute='_compute_manictime_hours',
        store=False,
        help='Billable hours tracked in ManicTime for this timesheet period'
    )
    
    manictime_activity_ids = fields.Many2many(
        'manictime.activity',
        string='ManicTime Activities',
        compute='_compute_manictime_activities',
        store=False,
        help='ManicTime activities matching this timesheet entry'
    )
    
    @api.depends('date', 'task_id', 'project_id', 'user_id', 'company_id')
    def _compute_manictime_activities(self):
        """Find ManicTime activities matching this timesheet entry"""
        # Check if exact tag matching is enabled
        use_exact_matching = self.env['ir.config_parameter'].sudo().get_param(
            'manictime_timesheet.exact_tag_matching', 'False'
        ).lower() in ('true', '1', 't')
        
        for line in self:
            if not line.project_id or not line.date or not line.user_id:
                line.manictime_activity_ids = False
                continue
                
            # Convert date to datetime range (full day in user's timezone)
            user_tz = pytz.timezone(line.user_id.tz or 'UTC')
            date_start = datetime.combine(line.date, datetime.min.time())
            date_start = user_tz.localize(date_start).astimezone(pytz.UTC)
            date_end = date_start + timedelta(days=1) - timedelta(seconds=1)
            
            # Find matching tag combinations differently based on configuration
            if use_exact_matching:
                # Use project code directly as the tag
                project_code = line.project_id.name.strip()
                
                # Find tag combinations matching the project code
                tag_combinations = self.env['manictime.tag.combination'].search([
                    ('user_id', '=', line.user_id.id),
                    '|',
                    ('name', '=', project_code),  # Exact match on name
                    ('tags', 'ilike', project_code)  # Tag is in the comma-separated list
                ])
            else:
                # Use the mapping system (original behavior)
                # Find all project mappings for this project/task
                mappings = self.env['manictime.project.mapping'].search([
                    '|', ('task_id', '=', line.task_id.id if line.task_id else False),
                         ('task_id', '=', False),
                    ('project_id', '=', line.project_id.id),
                    ('active', '=', True),
                    ('company_id', '=', line.company_id.id)
                ])
                
                if not mappings:
                    line.manictime_activity_ids = False
                    continue
                    
                # Get all ManicTime tag combinations for the mapped tags
                manictime_tags = [m.manictime_tag for m in mappings]
                
                # Find tag combinations for these tags
                tag_combinations = self.env['manictime.tag.combination'].search([
                    ('user_id', '=', line.user_id.id),
                    ('name', 'in', manictime_tags)
                ])
            
            if not tag_combinations:
                line.manictime_activity_ids = False
                continue
                
            # Find activities in the date range with matching tags
            activities = self.env['manictime.activity'].search([
                ('user_id', '=', line.user_id.id),
                ('start_time', '>=', date_start),
                ('end_time', '<=', date_end),
                ('tags_list', 'in', tag_combinations.ids),
            ])
            
            line.manictime_activity_ids = activities if activities else False
    
    @api.depends('manictime_activity_ids')
    def _compute_manictime_hours(self):
        """Calculate total billable hours from ManicTime activities"""
        for line in self:
            if not line.manictime_activity_ids:
                line.manictime_hours = 0.0
                continue
                
            # For activities to be billable, they must have a tag combination that's marked as billable
            # First, make sure tags_list is properly computed for each activity
            for activity in line.manictime_activity_ids:
                activity._compute_tags_list()
            
            # Filter billable activities - an activity is billable if ANY of its tag combinations is billable
            billable_activities = self.env['manictime.activity']
            for activity in line.manictime_activity_ids:
                if activity.tags_list and any(tag.is_billable for tag in activity.tags_list):
                    billable_activities |= activity
            
            total_hours = sum(activity.duration for activity in billable_activities)
            line.manictime_hours = float_round(total_hours, precision_digits=2)

    @api.model
    def grid_update_cell(self, domain, cell_field, value):
        """Extends the grid update to show manictime_hours in the response"""
        result = super().grid_update_cell(domain, cell_field, value)
        # Add the ManicTime hours for each timesheet in the response
        if result and 'data' in result:
            # Fetch the updated records
            if 'records' in result['data']:
                record_ids = [r['id'] for r in result['data']['records']]
                records = self.browse(record_ids)

                # Add the ManicTime hours to each record
                for i, record in enumerate(records):
                    # Force recompute the manictime fields
                    record._compute_manictime_activities()
                    record._compute_manictime_hours()

                    # Add the manictime_hours to the response
                    result['data']['records'][i]['manictime_hours'] = record.manictime_hours

        return result