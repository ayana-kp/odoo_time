{
    'name': 'ManicTime',
    'version': '18.0.0.1.1',
    'category': 'Productivity',
    'summary': 'Integrate ManicTime with Odoo - Time tracking and activity sync',
    'sequence': 10,
    'description': """
ManicTime Integration
=====================
This module integrates ManicTime with Odoo, allowing for time tracking and synchronization.

Features:
- Connect to ManicTime Server (supports Bearer Token and NTLM authentication)
- Configure per-user ManicTime connections
- Sync activities from all timelines for the configured period
- Sync tag combinations for better organization
- View and analyze time tracking data with tags
- Integration with tasks and timesheet
    """,
    'author': 'Harrison Consulting',
    'website': 'https://www.example.com',
    'depends': ['base', 'project', 'timesheet_grid', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/manictime_schema_views.xml',
        'views/manictime_environment_views.xml',
        'views/manictime_config_views.xml',
        'views/res_config_settings_views.xml',
        'views/manictime_link_views.xml',
        'views/manictime_user_timeline_views.xml',
        'views/manictime_activity_views.xml',
        'views/manictime_tag_views.xml',
        'views/res_users_views.xml',
        'views/menus.xml',  # Menu definitions must be loaded after the views they reference
        'data/manictime_cron.xml',
        'data/manictime_auth_cron.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
        ],
    },
}
