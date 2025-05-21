# ManicTime Timesheet Integration

This module integrates ManicTime billable hours with Odoo timesheets, displaying ManicTime data directly in the timesheet grid view.

## Features

- Display ManicTime billable hours beneath Odoo timesheet entries in grid view
- Map ManicTime tag combinations to Odoo projects and tasks
- Show detailed ManicTime activities on timesheet forms
- Compare tracked time in ManicTime vs. hours logged in Odoo

## Configuration

1. Go to ManicTime > Configuration > Project Mappings
2. Create mappings between ManicTime tags (e.g., "038", "042") and Odoo projects/tasks
3. Only billable activities from ManicTime will be counted in the grid view

## Usage

After configuring the mappings, the timesheet grid view will automatically show:
- Regular timesheet entries (editable)
- ManicTime billable hours beneath each entry (read-only)

This makes it easy to see where you need to add timesheet entries to match your tracked time in ManicTime.

## Technical Details

The module:
1. Creates a mapping model between ManicTime tags and Odoo projects
2. Extends the account.analytic.line model with ManicTime data
3. Customizes the grid view to display both values
4. Only includes billable time from ManicTime tags

## Dependencies

- manictime_server: Base ManicTime integration
- hr_timesheet: Base timesheet functionality  
- timesheet_grid: Enterprise grid view for timesheets