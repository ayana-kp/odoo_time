from odoo import models, fields, api, _

class ManicTimeProjectMapping(models.Model):
    _name = 'manictime.project.mapping'
    _description = 'ManicTime Project Mapping'
    
    name = fields.Char(string='Name', compute='_compute_name', store=True,
                      help='Automatically generated name based on project and tag')
    project_id = fields.Many2one('project.project', string='Odoo Project', required=True, 
                                help='The Odoo project to associate with this ManicTime tag')
    task_id = fields.Many2one('project.task', string='Odoo Task', 
                             help='Specific task to associate with this ManicTime tag (optional)')
    manictime_tag = fields.Char(string='ManicTime Tag', required=True,
                              help='Tag code used in ManicTime (e.g., "038", "042")')
    active = fields.Boolean(string='Active', default=True, 
                          help='Whether this mapping is active')
    company_id = fields.Many2one('res.company', string='Company', 
                               default=lambda self: self.env.company)
    
    _sql_constraints = [
        ('manictime_tag_company_uniq', 'unique(manictime_tag, company_id)', 
         'A mapping for this ManicTime tag already exists in this company!')
    ]
    
    @api.depends('project_id', 'task_id', 'manictime_tag')
    def _compute_name(self):
        """Generate a name based on the project, task, and tag"""
        for record in self:
            if record.task_id:
                record.name = f"{record.project_id.name} - {record.task_id.name} ({record.manictime_tag})"
            else:
                record.name = f"{record.project_id.name} ({record.manictime_tag})"
                
    def get_mapped_project_task(self, tag_name):
        """Find the project and task for a given ManicTime tag"""
        mapping = self.search([
            ('manictime_tag', '=', tag_name),
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if mapping:
            return mapping.project_id, mapping.task_id
        return False, False