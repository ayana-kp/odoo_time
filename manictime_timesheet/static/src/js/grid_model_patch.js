/** @odoo-module */

import { patch } from "@web/core/utils/patch";

const modelProto = owl.Component.prototype;

/**
 * Patch grid models to add ManicTime hours to the data
 */
patch(modelProto, "manictime_timesheet.model_extension", {
    /**
     * Check if this is a model we should extend
     */
    _isGridModel() {
        return (
            this.metaData && 
            this.metaData.resModel && 
            this._fetchData && 
            typeof this._fetchData === 'function'
        );
    },
    
    /**
     * @override
     */
    async _fetchData() {
        // Call the original method
        const result = await this._super.apply(this, arguments);
        
        // Only process account.analytic.line records
        if (this._isGridModel() && this.metaData.resModel === 'account.analytic.line') {
            // Add manictime_hours to records if needed
            if (result?.data?.records) {
                for (const record of result.data.records) {
                    if (record && !('manictime_hours' in record)) {
                        record.manictime_hours = 0.0;
                    }
                }
            }
        }
        
        return result;
    }
});