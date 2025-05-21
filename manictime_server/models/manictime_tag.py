from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ManicTimeTagCombination(models.Model):
    _name = 'manictime.tag.combination'
    _description = 'ManicTime Tag Combination'
    _auto = True  # Still create the table in the database
    
    name = fields.Char(string='Name', required=True, 
                      help='Name of the tag combination in ManicTime')
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade',
                            help='User who owns this tag combination')
    entity_id = fields.Char(string='Entity ID', 
                          help='Entity ID from ManicTime server')
    tags = fields.Char(string='Tags', 
                     help='Comma-separated list of tags in this combination')
    description = fields.Text(string='Description')
    color = fields.Char(string='Color', 
                       help='Hex color code for the tag combination')
    is_billable = fields.Boolean(string='Billable', default=False,
                          help='Whether this tag is marked as billable in ManicTime')
    
    _sql_constraints = [
        ('user_entity_id_uniq', 'unique(user_id, entity_id)', 
         'Tag combination must be unique per user!')
    ]

    def name_get(self):
        """Custom name display including tags"""
        result = []
        for record in self:
            tag_list = record.tags or ""
            result.append((record.id, f"{record.name} ({tag_list})"))
        return result
        
    @api.model_create_multi
    def create(self, vals_list):
        """Prevent manual creation of records"""
        # Allow creation only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("Tag combinations cannot be created manually. They are synchronized automatically from ManicTime server."))
        return super(ManicTimeTagCombination, self).create(vals_list)
        
    def write(self, vals):
        """Prevent manual updates to records"""
        # Allow updates only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("Tag combinations cannot be modified manually. They are synchronized automatically from ManicTime server."))
        return super(ManicTimeTagCombination, self).write(vals)
        
    def unlink(self):
        """Prevent manual deletion of records"""
        # Allow deletion only from authorized code paths
        calling_method = self.env.context.get('calling_method')
        if not calling_method or calling_method != 'manictime_sync':
            raise UserError(_("Tag combinations cannot be deleted manually. They are managed automatically through synchronization."))
        return super(ManicTimeTagCombination, self).unlink()