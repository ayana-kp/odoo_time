/** @odoo-module */

import { GridDataPoint } from "@web_grid/views/grid_model";
import { TimesheetGridDataPoint, TimesheetGridModel } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_model";

/**
 * Extends the TimesheetGridDataPoint to include ManicTime hours in the data
 */
export class ManicTimeGridDataPoint extends TimesheetGridDataPoint {
    /**
     * @override
     */
    async fetchData() {
        const result = await super.fetchData();
        
        // Add ManicTime hours to records if they don't already have it
        if (result?.data?.records) {
            for (const record of result.data.records) {
                if (record && !('manictime_hours' in record)) {
                    record.manictime_hours = 0.0;
                }
            }
        }
        
        return result;
    }
}

/**
 * Extends the TimesheetGridModel to use our custom data point class
 */
export class ManicTimeGridModel extends TimesheetGridModel {
    static DataPoint = ManicTimeGridDataPoint;
}