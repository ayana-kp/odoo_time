from odoo import models, fields, api

class ManicTimeSchema(models.Model):
    _name = 'manictime.schema'
    _description = 'ManicTime Schema'
    _rec_name = 'display_name'
    _order = 'name, version'
    
    name = fields.Char(
        string='Schema Name',
        required=True,
        help='Name of the schema (e.g., ManicTime/Documents)'
    )
    version = fields.Char(
        string='Version',
        required=True,
        help='Schema version number'
    )
    base_schema_id = fields.Many2one(
        'manictime.schema',
        string='Base Schema',
        help='Reference to the base schema, if applicable'
    )
    timeline_ids = fields.One2many(
        'manictime.user.timeline',
        'schema_id',
        string='Timelines',
        help='Timelines using this schema'
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        help='Schema name with version for display'
    )
    
    _sql_constraints = [
        ('name_version_uniq', 'unique(name, version)', 'Schema name and version combination must be unique!')
    ]
    
    @api.depends('name', 'version', 'base_schema_id')
    def _compute_display_name(self):
        for schema in self:
            base_info = ""
            if schema.base_schema_id and schema.base_schema_id.name:
                base_info = f" (Base: {schema.base_schema_id.name})"
                
            schema.display_name = f"{schema.name} v{schema.version}{base_info}" if schema.name and schema.version else ""
    
    def name_get(self):
        result = []
        for schema in self:
            name = schema.display_name or f"{schema.name} v{schema.version}"
            result.append((schema.id, name))
        return result