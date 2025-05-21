import logging
import re
from datetime import datetime
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Fix activities with timezone information in start_time or end_time fields"""
    if not version:
        return

    _logger.info("Starting migration to fix activities with timezone information")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Find all activities that might have timezone issues
    # We can't directly query for them, but we can look for patterns in the database
    # that might indicate timezone strings: e.g., '+00:00' or '-04:00' suffixes
    
    query = """
    SELECT id, start_time, end_time 
    FROM manictime_activity 
    WHERE start_time::text LIKE '%+%' OR start_time::text LIKE '%-%:%' 
    OR end_time::text LIKE '%+%' OR end_time::text LIKE '%-%:%'
    """
    
    cr.execute(query)
    problematic_activities = cr.fetchall()
    
    _logger.info(f"Found {len(problematic_activities)} activities with potential timezone issues")
    
    fixed_count = 0
    failed_count = 0
    
    for activity_id, start_time, end_time in problematic_activities:
        try:
            updates = {}
            
            # Process start_time
            if start_time:
                start_str = str(start_time)
                if ('+' in start_str or ('-' in start_str and ':' in start_str)) and 'T' in start_str:
                    # Try to remove timezone information
                    match = re.match(r'(.+)(?:[+-][\d:]+)$', start_str)
                    if match:
                        naive_dt_str = match.group(1)
                        # Convert to proper datetime object
                        if 'T' in naive_dt_str:
                            naive_dt = datetime.fromisoformat(naive_dt_str.replace('T', ' '))
                        else:
                            naive_dt = datetime.fromisoformat(naive_dt_str)
                        updates['start_time'] = naive_dt
            
            # Process end_time
            if end_time:
                end_str = str(end_time)
                if ('+' in end_str or ('-' in end_str and ':' in end_str)) and 'T' in end_str:
                    # Try to remove timezone information
                    match = re.match(r'(.+)(?:[+-][\d:]+)$', end_str)
                    if match:
                        naive_dt_str = match.group(1)
                        # Convert to proper datetime object
                        if 'T' in naive_dt_str:
                            naive_dt = datetime.fromisoformat(naive_dt_str.replace('T', ' '))
                        else:
                            naive_dt = datetime.fromisoformat(naive_dt_str)
                        updates['end_time'] = naive_dt
            
            # Update the activity if we have changes
            if updates:
                # Use direct SQL to bypass ORM validation
                update_parts = []
                params = []
                
                for field, value in updates.items():
                    update_parts.append(f"{field} = %s")
                    params.append(value)
                
                # Add the activity ID to params
                params.append(activity_id)
                
                update_query = f"""
                UPDATE manictime_activity 
                SET {', '.join(update_parts)} 
                WHERE id = %s
                """
                
                cr.execute(update_query, params)
                fixed_count += 1
                
        except Exception as e:
            _logger.error(f"Error fixing activity {activity_id}: {str(e)}")
            failed_count += 1
    
    _logger.info(f"Migration complete: fixed {fixed_count} activities, failed to fix {failed_count} activities")