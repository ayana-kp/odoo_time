/** @odoo-module */

import { TimesheetGridRenderer } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_renderer";
import { registry } from "@web/core/registry";
import { manicTimeGridCell } from "../components/manictime_grid_cell/manictime_grid_cell";

/**
 * Extends the TimesheetGridRenderer to use our custom cell component
 * and pass ManicTime hours to cells
 */
export class ManicTimeGridRenderer extends TimesheetGridRenderer {
    /**
     * @override
     */
    getCellProps(cell, options) {
        const props = super.getCellProps(cell, options);
        
        // Add ManicTime hours to the props if available
        if (cell?.record && 'manictime_hours' in cell.record) {
            props.manictime_hours = cell.record.manictime_hours;
        }
        
        return props;
    }
    
    /**
     * @override
     */
    getCellComponent(cell) {
        // Use our custom component for timesheet cells
        if (this.props.model._dataPoint.resModel === 'account.analytic.line') {
            // If it's a timesheet cell, use our custom component
            return manicTimeGridCell.component;
        }
        
        // Otherwise, use the default component
        return super.getCellComponent(cell);
    }
}