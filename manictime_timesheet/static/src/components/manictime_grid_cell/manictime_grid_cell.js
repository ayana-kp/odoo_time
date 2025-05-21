/** @odoo-module */

import { registry } from "@web/core/registry";
import { GridCell } from "@web_grid/components/grid_cell";
import { formatFloat } from "@web/core/utils/numbers";
import { useEffect } from "@odoo/owl";
console.log('hiiiiiiiii',GridCell)
/**
 * Extends GridCell to display ManicTime hours beneath the regular value
 */
export class ManicTimeGridCell extends GridCell {
//    static template = "web_grid.Cell";
    static props = {
        ...GridCell.props,
        manictime_hours: { type: Number, optional: true },
    };
    setup() {
        super.setup();
        console.log('this')
        useEffect(() => {
            if (this.rootRef.el && 'manictime_hours' in this.props && !this.state.edit) {
                this.updateManicTimeHours();
            }
        });
    }
    updateManicTimeHours() {
        console.log('testttt',this)
        if (!this.rootRef.el) {
            return;
        }
        const hasValue = (this.props.manictime_hours || 0) > 0;
        const valueDisplay = this.rootRef.el.querySelector('.d-flex span.z-1');
        
        if (!valueDisplay || this.state.edit) {
            return;
        }
        
        // Remove any existing ManicTime display
        const existingMT = this.rootRef.el.querySelector('.o_grid_manictime_hours');
        if (existingMT) {
            existingMT.remove();
        }
        
        // Only add a display if we have a value
        if (hasValue) {
            const container = valueDisplay.parentNode;
            const formattedValue = formatFloat(this.props.manictime_hours || 0, { digits: 2 });
            
            // Create the display HTML
            const html = `
                <div class="mt-1 o_grid_manictime_hours" 
                     style="color: #0d6efd; font-size: 0.85em;" 
                     title="ManicTime Billable Hours: ${this.props.manictime_hours}">
                    <span>MT: </span>
                    <span class="o_grid_cell_value">${formattedValue}</span>
                </div>
            `;
            
            // Add to DOM
            container.insertAdjacentHTML('beforeend', html);
        }
    }
}

// Register our custom cell component
export const manicTimeGridCell = {
    component: ManicTimeGridCell,
    formatter: formatFloat,
};

registry.category("grid_components").add("manictime_float", manicTimeGridCell);