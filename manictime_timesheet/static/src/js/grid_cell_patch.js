/** @odoo-module */

import { useManicTimeCell } from "../hooks/use_manictime_cell";
import { patch } from "@web/core/utils/patch";

const cellProto = owl.Component.prototype;

/**
 * Patch for any grid cell component to add ManicTime hours display capability
 * 
 * This is a simpler approach - we try to patch any Cell component that matches
 * certain criteria rather than attempting to extend specific grid components.
 */
patch(cellProto, "manictime_timesheet.cell_extension", {
    /**
     * Check if this is a component we should extend
     */
    _isGridCellComponent() {
        return (
            this.props && 
            this.props.reactive && 
            this.props.reactive.cell && 
            this.rootRef && 
            this.state && 
            typeof this.state.edit !== 'undefined'
        );
    },
    
    /**
     * Extend the component setup
     */
    setup() {
        // Call original setup
        this._super.apply(this, arguments);
        
        // Only apply to grid cell components
        if (this._isGridCellComponent()) {
            // Use our custom hook
            useManicTimeCell();
        }
    }
});