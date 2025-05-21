/** @odoo-module */

import { useComponent, useEffect } from "@odoo/owl";
import { formatFloat } from "@web/core/utils/numbers";

/**
 * Hook to add ManicTime hours to grid cells
 * 
 * This hook is designed to be used in components that display
 * timesheet grid cells, adding ManicTime hours display when available
 */
export function useManicTimeCell() {
    const component = useComponent();
    
    // Add effect to update the cell when mounted or updated
    useEffect(() => {
        if (component.rootRef?.el && 
            component.props && 
            'manictime_hours' in component.props && 
            !component.state.edit) {
            
            updateManicTimeHours();
        }
    });
    
    /**
     * Updates the cell DOM to display ManicTime hours
     */
    function updateManicTimeHours() {
        const rootEl = component.rootRef.el;
        if (!rootEl) return;
        
        const hasValue = (component.props.manictime_hours || 0) > 0;
        const valueDisplay = rootEl.querySelector('.d-flex span.z-1');
        
        if (!valueDisplay || component.state.edit) return;
        
        // Remove any existing ManicTime display
        const existingMT = rootEl.querySelector('.o_grid_manictime_hours');
        if (existingMT) {
            existingMT.remove();
        }
        
        // Only add display if we have a value
        if (hasValue) {
            const container = valueDisplay.parentNode;
            const formattedValue = formatFloat(component.props.manictime_hours || 0, { digits: 2 });
            
            // Create ManicTime hours HTML
            const html = `
                <div class="mt-1 o_grid_manictime_hours" 
                     style="color: #0d6efd; font-size: 0.85em;" 
                     title="ManicTime Billable Hours: ${component.props.manictime_hours}">
                    <span>MT: </span>
                    <span class="o_grid_cell_value">${formattedValue}</span>
                </div>
            `;
            
            // Add to DOM
            container.insertAdjacentHTML('beforeend', html);
        }
    }
    
    return {
        updateManicTimeHours,
    };
}