/** @odoo-module */

import { patch } from "@web/core/utils/patch";

const rendererProto = owl.Component.prototype;

/**
 * Patch grid renderers to add ManicTime hours to cell props
 */
patch(rendererProto, "manictime_timesheet.renderer_extension", {
    /**
     * Check if this is a renderer we should extend
     */
    _isGridRenderer() {
        return (
            this.props && 
            this.props.model && 
            this.getGridlikeComponents && 
            typeof this.getGridlikeComponents === 'function'
        );
    },
    
    /**
     * @override
     */
    getGridlikeComponents() {
        const result = this._super.apply(this, arguments);
        
        // Only process timesheets
        if (this._isGridRenderer() && 
            this.props.model.metaData && 
            this.props.model.metaData.resModel === 'account.analytic.line') {
            
            // Check if we have cellProps function
            if (result && typeof result.cellProps === 'function') {
                // Save original function
                const originalCellProps = result.cellProps;
                
                // Override with our enhanced version
                result.cellProps = (cell, options) => {
                    // Get original props
                    const props = originalCellProps(cell, options);
                    
                    // Add manictime_hours if we have a record
                    if (cell?.record) {
                        props.manictime_hours = cell.record.manictime_hours ?? 0;
                    }
                    
                    return props;
                };
            }
        }
        
        return result;
    }
});