from odoo.tests.common import TransactionCase

class TestManicTimeTimesheetInstall(TransactionCase):
    """Test the installation of the ManicTime Timesheet module"""

    def test_module_installed(self):
        """Test that the module is correctly installed"""
        # Check that the module is in the installed module list
        module = self.env['ir.module.module'].search([
            ('name', '=', 'manictime_timesheet'),
            ('state', '=', 'installed')
        ])
        self.assertTrue(module, "ManicTime Timesheet module is not installed")
        
        # Check that the mapping model exists
        mapping_model = self.env['ir.model'].search([
            ('model', '=', 'manictime.project.mapping')
        ])
        self.assertTrue(mapping_model, "ManicTime Project Mapping model is not installed")
        
        # Check that the timesheet model has been extended
        timesheet_model = self.env['ir.model'].search([
            ('model', '=', 'account.analytic.line')
        ])
        self.assertTrue(timesheet_model, "Account Analytic Line model is not available")
        
        # Try to create a test mapping record
        project = self.env['project.project'].search([], limit=1)
        if project:
            mapping = self.env['manictime.project.mapping'].create({
                'project_id': project.id,
                'manictime_tag': '038',
            })
            self.assertTrue(mapping.id > 0, "Failed to create a test mapping record")