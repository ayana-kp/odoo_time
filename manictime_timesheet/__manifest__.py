{
    'name': "ManicTime Timesheet Integration",
    'summary': "Integrate ManicTime billable hours with Odoo timesheets",
    'description': """
        Display ManicTime billable hours beneath Odoo timesheet entries in grid view.
        This allows for easy comparison between time tracked in ManicTime and
        time logged in Odoo timesheets.
    """,
    'author': "Harrison Consulting",
    'website': "https://www.harrisonconsulting.co",
    'category': 'Services/Timesheets',
    'version': '1.0.3',
    'depends': [
        'manictime_server',  # Base ManicTime integration
        'hr_timesheet',      # Base timesheet functionality
        'timesheet_grid',    # Enterprise grid view for timesheets
        'web_grid',          # Explicitly depend on web_grid for templates
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/manictime_project_mapping_views.xml',
        'views/hr_timesheet_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend_lazy':[
            # Component extensions
            ('after', 'web_grid/static/src/components/grid_cell.js', 'manictime_timesheet/static/src/components/**/*.js'),
            # Model and renderer extensions
            ('after', 'timesheet_grid/static/src/views/timesheet_grid/timesheet_grid_model.js', 'manictime_timesheet/static/src/js/timesheet_grid_model.js'),
            ('after', 'timesheet_grid/static/src/views/timesheet_grid/timesheet_grid_renderer.js', 'manictime_timesheet/static/src/js/timesheet_grid_renderer.js'),
            # View registration
            ('after', 'timesheet_grid/static/src/views/timesheet_grid/timesheet_grid_view.js', 'manictime_timesheet/static/src/views/manictime_timesheet_grid_view.js'),
        ],
    },
    'post_init_hook': 'post_init_hook',
    'application': False,
    'license': 'LGPL-3',
}
