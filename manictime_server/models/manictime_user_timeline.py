from odoo import models, fields, api

class ManicTimeUserTimeline(models.Model):
    _name = 'manictime.user.timeline'
    _description = 'ManicTime User Timeline'
    _order = 'name'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        help='The user who owns this timeline'
    )
    # Primary key from API - we use this for all interactions
    timeline_key = fields.Char(
        string='Timeline Key',
        required=True,
        index=True,
        help='Primary key used for API requests (timelineKey in API)'
    )
    # Legacy field, kept for backward compatibility
    timeline_id = fields.Char(
        string='Legacy Timeline ID',
        help='Legacy identifier, kept for backward compatibility'
    )
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        help='Display name for the timeline'
    )

    # Environment string field (for backward compatibility)
    environment_id_str = fields.Char(
        string='Environment ID String',
        help='String identifier for the environment (legacy field)',
        readonly=True
    )

    # Environment relationship - new model reference
    environment_id = fields.Many2one(
        'manictime.environment',
        string='Environment',
        ondelete='set null',
        help='Device environment this timeline belongs to'
    )
    device_display_name = fields.Char(
        string='Device Display Name',
        help='Display name of the device in ManicTime'
    )

    # Schema relationship - new model reference
    schema_id = fields.Many2one(
        'manictime.schema',
        string='Schema',
        ondelete='set null',
        help='Schema information for this timeline'
    )
    timeline_type = fields.Char(
        string='Type',
        compute='_compute_timeline_type',
        store=True,
        help='Type of this timeline (e.g., ComputerUsage, Applications, etc.)'
    )

    # Owner fields
    owner_username = fields.Char(
        string='Owner Username',
        help='Username of the timeline owner'
    )
    owner_display_name = fields.Char(
        string='Owner Display Name',
        help='Display name of the timeline owner'
    )

    # Update fields
    last_update = fields.Datetime(
        string='Last Updated',
        help='When this timeline was last updated in ManicTime'
    )
    last_change_id = fields.Char(
        string='Last Change ID',
        help='ID of the last change in ManicTime'
    )

    # Additional fields directly from API
    publish_key = fields.Char(
        string='Publish Key',
        help='Publishing key for this timeline (publishKey in API)'
    )
    update_protocol = fields.Char(
        string='Update Protocol',
        help='Protocol used for timeline updates (updateProtocol in API)'
    )
    timestamp = fields.Char(
        string='Timestamp',
        help='Timeline timestamp information'
    )

    # Sync status fields
    is_selected = fields.Boolean(
        string='Selected',
        default=True,
        help='Whether this timeline is selected for synchronization'
    )
    last_sync = fields.Datetime(
        string='Last Sync',
        help='When this timeline was last synchronized'
    )
    activity_count = fields.Integer(
        string='Activities',
        compute='_compute_activity_count',
        help='Number of activities in this timeline'
    )

    # Links to API - now managed by manictime.link model
    link_ids = fields.Many2many(
        'manictime.link',
        'manictime_timeline_link_rel',
        'timeline_id',
        'link_id',
        string='API Capabilities',
        help='API capabilities available for this timeline'
    )

    _sql_constraints = [
        ('user_timeline_key_uniq', 'unique(user_id, timeline_key)', 'Timeline key must be unique per user!')
    ]

    @api.depends('device_display_name', 'environment_id.device_name', 'timeline_type')
    def _compute_name(self):
        for timeline in self:
            device_name = timeline.device_display_name or (timeline.environment_id and timeline.environment_id.device_name) or ''
            timeline_type = timeline.timeline_type or ''

            if device_name and timeline_type:
                timeline.name = f"{device_name} - {timeline_type}"
            elif device_name:
                timeline.name = device_name
            elif timeline_type:
                timeline.name = timeline_type
            else:
                timeline.name = timeline.timeline_key[:8] if timeline.timeline_key else "Unnamed Timeline"

    @api.depends('schema_id.name')
    def _compute_timeline_type(self):
        for timeline in self:
            if timeline.schema_id and timeline.schema_id.name:
                # Extract type from schema name (e.g., "ManicTime/Documents" -> "Documents")
                schema_parts = timeline.schema_id.name.split('/')
                if schema_parts:
                    timeline.timeline_type = schema_parts[-1]
                else:
                    timeline.timeline_type = timeline.schema_id.name
            else:
                timeline.timeline_type = False

    def toggle_selection(self):
        for record in self:
            record.is_selected = not record.is_selected

    def _compute_activity_count(self):
        for record in self:
            record.activity_count = self.env['manictime.activity'].search_count([
                ('timeline_id', '=', record.id)
            ])

    def name_get(self):
        result = []
        for timeline in self:
            display_name = timeline.name or f"{timeline.timeline_key[:8]}"
            result.append((timeline.id, display_name))
        return result

    def get_link_url(self, rel_type):
        """Get the URL for a specific relation type"""
        self.ensure_one()
        link = self.env['manictime.link'].search([
            ('timeline_ids', 'in', [self.id]),
            ('rel', '=', rel_type)
        ], limit=1)

        if not link or not link.pattern or not self.timeline_key:
            return False

        # Replace placeholders with actual values
        url = link.pattern
        url = url.replace('{timeline_key}', self.timeline_key)

        return url

    def get_activities_url(self):
        """Get the activities URL for this timeline"""
        return self.get_link_url('manictime/activities')

    def get_changes_url(self):
        """Get the changes URL for this timeline"""
        return self.get_link_url('manictime/getchanges')

    def get_add_changes_url(self):
        """Get the URL for adding changes to this timeline"""
        return self.get_link_url('manictime/addchanges')

    def action_view_activities(self):
        """Open the activities view for this timeline"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Activities',
            'res_model': 'manictime.activity',
            'view_mode': 'list,form',
            'domain': [('timeline_id', '=', self.id)],
            'context': {'default_timeline_id': self.id},
            'path': f'manictime-timeline-{self.id}-activities'
        }

    def action_sync_timeline(self):
        """Sync just this timeline"""
        self.ensure_one()
        return self.user_id.with_context(active_timeline_id=self.id).manictime_sync_data()
