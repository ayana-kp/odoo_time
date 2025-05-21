/** @odoo-module */

import { registry } from "@web/core/registry";
import { timesheetGridView } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_view";
import { ManicTimeGridModel } from "../js/timesheet_grid_model";
import { ManicTimeGridRenderer } from "../js/timesheet_grid_renderer";

// Register our custom timesheet grid view that includes ManicTime hours
registry.category("views").add("manictime_timesheet_grid", {
    ...timesheetGridView,
    Model: ManicTimeGridModel,
    Renderer: ManicTimeGridRenderer,
});