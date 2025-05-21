from odoo import models, fields, api
import re

class ManicTimeLink(models.Model):
    _name = 'manictime.link'
    _description = 'ManicTime API Link Capability'
    _rec_name = 'rel'
    _order = 'rel'

    rel = fields.Char(
        string='Relation',
        required=True,
        help='API endpoint relation type (e.g., self, manictime/activities)'
    )
    pattern = fields.Char(
        string='URL Pattern',
        help='URL pattern with {timeline_key} as placeholder'
    )

    # Many2many relationship with timelines
    timeline_ids = fields.Many2many(
        'manictime.user.timeline',
        'manictime_timeline_link_rel',
        'link_id',
        'timeline_id',
        string='Timelines',
        help='Timelines that have this capability'
    )

    # Count of timelines with this capability
    timeline_count = fields.Integer(
        string='Timeline Count',
        compute='_compute_timeline_count',
        store=True,
        help='Number of timelines with this capability'
    )

    _sql_constraints = [
        ('rel_uniq', 'unique(rel, pattern)', 'The combination of relation type and URL pattern must be unique!')
    ]

    @api.depends('timeline_ids')
    def _compute_timeline_count(self):
        for record in self:
            record.timeline_count = len(record.timeline_ids)


    def name_get(self):
        result = []
        for link in self:
            name = f"{link.rel}"
            result.append((link.id, name))
        return result

    @api.model
    def get_link_url(self, timeline, rel_type):
        """Generate the URL for a specific relation type and timeline

        Instead of retrieving a stored URL, this method now dynamically generates
        the URL by replacing placeholders in the pattern with actual values.
        """
        # Find links with this rel_type that are associated with the timeline
        link = self.search([
            ('rel', '=', rel_type),
            ('timeline_ids', 'in', [timeline.id])
        ], limit=1)

        if not link or not link.pattern:
            return False

        # Replace placeholders with actual values
        url = link.pattern

        # Replace timeline_key placeholder if present
        if '{timeline_key}' in url and timeline.timeline_key:
            url = url.replace('{timeline_key}', timeline.timeline_key)

        # Replace any other relevant placeholders...

        return url

    @api.model
    def extract_url_pattern(self, url, timeline_key):
        """Extract a reusable URL pattern from a full URL by replacing the timeline key with a placeholder"""
        if not url or not timeline_key:
            return url

        # Replace the actual timeline key with a placeholder
        pattern = url.replace(timeline_key, '{timeline_key}')

        return pattern
