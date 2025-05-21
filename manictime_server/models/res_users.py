from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, timedelta
import uuid
import hashlib
# Try to import keyring but don't fail if not available
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
import base64

_logger = logging.getLogger(__name__)

def generate_key_id(user_id):
    """Generate a unique key ID for keyring storage based on user ID"""
    return f"odoo_manictime_{user_id}"

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _compute_access_token_status(self):
        """Compute whether an access token is available"""
        for user in self:
            has_token = bool(self.env['manictime.token.storage'].get_secret(user.id, 'access_token'))
            user.manictime_access_token = "Available" if has_token else "Not Available"

    # Computed field to show whether the user has ManicTime enabled
    # Simply check if a configuration exists
    manictime_enabled = fields.Boolean(
        string='ManicTime Enabled',
        compute='_compute_manictime_enabled',
        store=True,
        help='Whether ManicTime integration is enabled for this user',
    )
    # Temporary field for authentication - not stored in database
    manictime_temp_secret = fields.Char(
        string='Client Secret / Password',
        help='Temporary field for authentication - not stored in database',
    )
    # Access token is stored in secure storage, not in the database
    # This is a computed field for display purposes only
    manictime_access_token = fields.Char(
        string='Access Token Status',
        compute='_compute_access_token_status',
        help='Indicates whether an access token is available',
        readonly=True,
    )

    # Computed fields that reference the manictime.config model
    @api.depends('manictime_config_id')
    def _compute_manictime_enabled(self):
        for user in self:
            config = self.env['manictime.config'].sudo().search_count([('user_id', '=', user.id)])
            user.manictime_enabled = bool(config)

    # Related fields to access configuration
    manictime_config_id = fields.One2many(
        'manictime.config', 'user_id',
        string='ManicTime Configuration',
    )
    manictime_auth_type = fields.Selection(
        related='manictime_config_id.auth_type',
        readonly=True,
        string='Authentication Type',
    )
    manictime_client_id_username = fields.Char(
        related='manictime_config_id.client_id_username',
        readonly=True,
        string='Client ID / Username',
    )
    manictime_token_expiry = fields.Datetime(
        related='manictime_config_id.token_expiry',
        readonly=True,
        string='Token Expiry',
    )
    manictime_last_sync = fields.Datetime(
        related='manictime_config_id.last_sync',
        readonly=True,
        string='Last Sync',
    )
    manictime_timeline_ids = fields.One2many(
        'manictime.user.timeline',
        'user_id',
        string='ManicTime Timelines'
    )

    @api.model
    def get_manictime_server_url(self):
        """Get the configured ManicTime server URL"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'manictime_server.server_url',
            default='https://manictime-server.example.com'
        )

    def _get_manictime_secret(self):
        """Securely retrieve the stored secret for ManicTime authentication"""
        self.ensure_one()

        # Use the token storage service
        return self.env['manictime.token.storage'].get_secret(self.id, 'client_secret')

    def _set_manictime_secret(self, secret):
        """Securely store the secret for ManicTime authentication"""
        self.ensure_one()
        if not secret:
            return

        # Use the token storage service
        return self.env['manictime.token.storage'].store_secret(self.id, secret, 'client_secret')

    def manictime_authenticate(self):
        """Attempt to authenticate with ManicTime server"""
        self.ensure_one()

        try:
            # Get the user's ManicTime config
            config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)

            if not config:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('ManicTime integration is not enabled for this user.'),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            server_url = self.get_manictime_server_url()
            if not server_url:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('ManicTime server URL is not configured.'),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            # If a temporary secret/password was provided, store it securely
            if self.manictime_temp_secret:
                self._set_manictime_secret(self.manictime_temp_secret)
                # Clear the temporary field
                self.write({'manictime_temp_secret': False})

            # Get the stored secret
            secret = self._get_manictime_secret()
            if not secret:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Authentication credentials not found. Please provide them again.'),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            # Import ManicTime client libraries
            try:
                import sys
                import os
                # Add the path to the manictime library
                server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manictime_path = os.path.join(server_path, 'manictime')
                if manictime_path not in sys.path:
                    sys.path.append(manictime_path)

                # Now import from manictime library
                from ..manictime.client import ManicTimeClient
                from ..manictime.configuration import Config
                from exceptions import AuthenticationError, ManicTimeClientError
            except ImportError as e:
                _logger.error(f"Failed to import ManicTime client libraries: {str(e)}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Failed to load ManicTime client: %s') % str(e),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            # Create authentication configuration
            if self.manictime_auth_type == 'bearer':
                if not self.manictime_client_id_username:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error'),
                            'message': _('Client ID is required for Bearer authentication.'),
                            'type': 'danger',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                                'infos': {'effect': {'type': 'reload'}}
                            }
                        }
                    }

                # Create config for token request
                config = Config(
                    server_url=server_url,
                    auth_type=self.manictime_auth_type,
                    username=self.manictime_client_id_username,  # Client ID as username for OAuth
                    password=secret,  # Stored secret as password/client_secret
                    timeout=30
                )

            elif self.manictime_auth_type == 'ntlm':
                if not self.manictime_client_id_username:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error'),
                            'message': _('Username is required for NTLM authentication.'),
                            'type': 'danger',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                                'infos': {'effect': {'type': 'reload'}}
                            }
                        }
                    }

                # Create config for NTLM authentication
                config = Config(
                    server_url=server_url,
                    auth_type='ntlm',
                    username=self.manictime_client_id_username,
                    password=secret,
                    timeout=30
                )

            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Invalid authentication type.'),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            # Create client and try authentication
            try:
                client = ManicTimeClient(config)

                if self.manictime_auth_type == 'bearer':
                    # Force token refresh
                    client._get_token()

                    # Extract token from client headers
                    auth_header = client.session.headers.get('Authorization', '')

                    if auth_header.startswith('Bearer '):
                        access_token = auth_header[7:]  # Remove 'Bearer ' prefix

                        # Store token information (with 1 day expiry as default - more conservative)
                        expiry = datetime.now() + timedelta(days=1)

                        # Store the access token in secure storage
                        self.env['manictime.token.storage'].store_secret(self.id, access_token, 'access_token')

                        # Store expiry in the config record
                        config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)
                        if config:
                            config.write({
                                'token_expiry': expiry
                            })
                    else:
                        raise AuthenticationError("No valid bearer token found in response")

                # Verify authentication works by fetching timelines and tags
                timeline_count = 0
                tag_count = 0

                try:
                    # Get timelines from the server
                    timeline_response = client.get_timelines()
                    _logger.info(f"Retrieved timeline response: {type(timeline_response)}")

                    # Add verbose logging to see the actual response structure
                    import pprint
                    _logger.info("VERBOSE RESPONSE LOGGING - Timeline Response Structure:")
                    if isinstance(timeline_response, dict):
                        _logger.info(f"Dictionary keys: {list(timeline_response.keys())}")
                        for key, value in timeline_response.items():
                            if isinstance(value, list) and value:
                                _logger.info(f"List content in key '{key}': {len(value)} items")
                                if value:
                                    _logger.info(f"First item in '{key}': {pprint.pformat(value[0])}")
                            elif isinstance(value, dict):
                                _logger.info(f"Dict content in key '{key}': {list(value.keys())}")
                    elif isinstance(timeline_response, list) and timeline_response:
                        _logger.info(f"List response with {len(timeline_response)} items")
                        if timeline_response:
                            _logger.info(f"First item: {pprint.pformat(timeline_response[0])}")
                    else:
                        _logger.info(f"Raw response: {pprint.pformat(timeline_response)}")

                    # Always sync tags first (before timelines) to ensure they're available
                    _logger.info("Syncing tag combinations as part of authentication")
                    try:
                        tags_result = self._sync_manictime_tags(client)
                        tag_count = len(tags_result)
                        _logger.info(f"Synchronized {tag_count} tag combinations during authentication")
                    except Exception as tag_error:
                        _logger.error(f"Tag sync error during authentication: {str(tag_error)}")
                        tag_count = 0
                        # Continue with timeline sync even if tag sync fails

                    # Use the improved _fetch_manictime_timelines method to process the response
                    # This method now handles dictionary responses and extracts timeline data properly
                    timelines_result = self._fetch_manictime_timelines(client, timeline_response)

                    # Get a count of timelines for the success message
                    timeline_count = len(timelines_result)

                except Exception as timeline_error:
                    _logger.error(f"Timeline fetch or processing error: {str(timeline_error)}")
                    # Still consider authentication successful if we got token

                # Set expiry for NTLM authentication
                config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)
                if config and config.auth_type == 'ntlm':
                    # No token for NTLM, but we'll set a success timestamp
                    config.write({
                        'token_expiry': datetime.now() + timedelta(days=7)  # 7 days validity for NTLM
                    })

                # Show success notification if not in silent mode
                if not self.env.context.get('suppress_notifications'):
                    message = _('Connected to ManicTime successfully! Found %s timelines and %s tag combinations.') % (timeline_count, tag_count)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': message,
                            'type': 'success',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                                'infos': {'effect': {'type': 'reload'}}
                            }
                        }
                    }
                return True

            except (AuthenticationError, ManicTimeClientError) as auth_error:
                _logger.error(f"ManicTime authentication error: {str(auth_error)}")
                # Show specific authentication error if not in silent mode
                if not self.env.context.get('suppress_notifications'):
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Authentication Failed'),
                            'message': _('Authentication failed: %s') % str(auth_error),
                            'type': 'danger',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                                'infos': {'effect': {'type': 'reload'}}
                            }
                        }
                    }
                return False

        except Exception as e:
            _logger.error(f"Unexpected error during ManicTime authentication: {str(e)}")
            # Show error notification for any other errors if not in silent mode
            if not self.env.context.get('suppress_notifications'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Unexpected error during authentication: %s') % str(e),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }
            return False

    def manictime_revoke_auth(self):
        """Revoke ManicTime authentication"""
        self.ensure_one()

        try:
            if not self.manictime_enabled:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('ManicTime integration is not enabled for this user.'),
                        'type': 'danger',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            # Clear authentication data from config
            config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)
            if config:
                config.write({
                    'token_expiry': False,
                    'last_sync': False,
                })

            # Delete all stored secrets
            token_storage = self.env['manictime.token.storage']
            token_storage.delete_secret(self.id, 'client_secret')  # Clear password/client secret
            token_storage.delete_secret(self.id, 'access_token')   # Clear access token
            token_storage.delete_secret(self.id, 'refresh_token')  # Clear refresh token if used

            # Clear temporary secret field to ensure it doesn't show up in the UI
            self.write({'manictime_temp_secret': False})

            # Show success notification and reload
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Authentication Revoked'),
                    'message': _('Your ManicTime authentication has been revoked and all stored credentials have been cleared.'),
                    'type': 'info',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                        'infos': {'effect': {'type': 'reload'}}
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error revoking ManicTime authentication: {str(e)}")

            # Show error notification and reload
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to revoke authentication: %s') % str(e),
                    'type': 'danger',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                        'infos': {'effect': {'type': 'reload'}}
                    }
                }
            }

    def _fetch_manictime_timelines(self, client, timelines=None):
        """Fetch and store ManicTime timelines"""
        self.ensure_one()

        try:
            if timelines is None:
                # If timelines weren't provided, fetch them
                timelines = client.get_timelines()

            # Handle various response formats with detailed logging
            if isinstance(timelines, dict):
                _logger.info("Timeline response is a dictionary, extracting timeline data")
                import pprint
                _logger.info(f"Dictionary keys: {list(timelines.keys())}")

                # Log the first few top-level values
                for key in list(timelines.keys())[:3]:  # Limit to first 3 keys to prevent log overflow
                    value = timelines[key]
                    _logger.info(f"Key: '{key}', Type: {type(value)}")
                    if isinstance(value, (dict, list)) and value:
                        _logger.info(f"Value sample for key '{key}': {pprint.pformat(value)[:500]}...")  # Limit output length

                # Handle common response patterns
                if 'timelines' in timelines:
                    _logger.info(f"Found 'timelines' key: {type(timelines['timelines'])}")
                    timelines = timelines.get('timelines', [])
                elif 'items' in timelines:
                    _logger.info(f"Found 'items' key: {type(timelines['items'])}")
                    timelines = timelines.get('items', [])
                elif 'data' in timelines:
                    _logger.info(f"Found 'data' key: {type(timelines['data'])}")
                    timelines = timelines.get('data', [])
                # Handle response with embedded list in a key that isn't one of the standard options
                elif any(isinstance(timelines.get(key), list) and timelines.get(key) for key in timelines.keys()):
                    # Find first key with a non-empty list
                    list_key = next((key for key in timelines.keys()
                                   if isinstance(timelines.get(key), list) and timelines.get(key)), None)
                    if list_key:
                        _logger.info(f"Using list from non-standard key: '{list_key}'")
                        timelines = timelines.get(list_key, [])
                # If we find any object with a timeline ID, try to use that
                elif 'timelineId' in timelines or 'id' in timelines:
                    _logger.info("Using dict itself as a single timeline object")
                    timelines = [timelines]
                # Other common response patterns - scan for common timeline-related terms
                elif any(key for key in timelines.keys() if 'timeline' in key.lower()):
                    timeline_key = next((key for key in timelines.keys() if 'timeline' in key.lower()), None)
                    _logger.info(f"Found timeline-related key: '{timeline_key}'")
                    if isinstance(timelines.get(timeline_key), list):
                        timelines = timelines.get(timeline_key, [])
                    elif isinstance(timelines.get(timeline_key), dict):
                        timelines = [timelines.get(timeline_key)]
                    else:
                        _logger.warning(f"Timeline key '{timeline_key}' doesn't contain list or dict")
                        return []
                else:
                    _logger.warning("Could not extract timeline data from response")
                    # For diagnostic purposes, log which keys look like potential candidates
                    for key, value in timelines.items():
                        if isinstance(value, (list, dict)):
                            _logger.info(f"Potential candidate key: '{key}' of type {type(value)}")
                    return []

            if not isinstance(timelines, list):
                _logger.warning(f"Expected list of timelines, got {type(timelines)}")
                return []

            result = []

            # Process timeline data in a transaction
            for timeline_data in timelines:
                try:
                    if not isinstance(timeline_data, dict):
                        _logger.warning(f"Invalid timeline data format: {type(timeline_data)}, skipping")
                        continue

                    try:
                        # Log the timeline data structure for debugging
                        import pprint
                        import json

                        # Create a more concise log with just essential fields
                        log_data = {
                            'timelineId': timeline_data.get('timelineId', timeline_data.get('id', 'unknown')),
                            'timelineKey': timeline_data.get('timelineKey', ''),
                            'name': timeline_data.get('name', ''),
                            'deviceDisplayName': timeline_data.get('deviceDisplayName', '')
                        }

                        # Add schema info if available
                        if 'schema' in timeline_data and isinstance(timeline_data['schema'], dict):
                            log_data['schema'] = {
                                'name': timeline_data['schema'].get('name', ''),
                                'version': timeline_data['schema'].get('version', '')
                            }

                        # Log the complete link structure to help with debugging
                        if 'links' in timeline_data and isinstance(timeline_data['links'], list):
                            log_data['links'] = timeline_data['links']

                        # Log in a more easily readable format for debugging
                        _logger.info(f"Timeline data (summary): {json.dumps(log_data, indent=2)}")
                    except Exception as log_error:
                        # If there's an error in logging, don't let it stop processing
                        _logger.warning(f"Error logging timeline data: {str(log_error)}")

                    # Use timelineKey as the primary identifier for timeline records
                    # This is more reliable and consistent with the API
                    timeline_key = timeline_data.get('timelineKey')

                    # For backward compatibility, still look for other ID fields, but prefer timelineKey
                    timeline_id = (
                        timeline_key or
                        timeline_data.get('timelineId') or
                        timeline_data.get('id') or
                        timeline_data.get('timeline_id')
                    )

                    # If we still don't have an ID, check for nested structure
                    if not timeline_id and isinstance(timeline_data.get('timeline'), dict):
                        nested_timeline = timeline_data.get('timeline')
                        timeline_id = (
                            nested_timeline.get('timelineKey') or
                            nested_timeline.get('timelineId') or
                            nested_timeline.get('id')
                        )
                        _logger.info(f"Extracted ID from nested timeline: {timeline_id}")

                    # If we still don't have an ID, use a hash of the timeline name and device
                    # This is better than random UUIDs for consistency between syncs
                    if not timeline_id:
                        _logger.warning(f"Timeline missing ID, generating a deterministic ID")
                        name = timeline_data.get('name', '')
                        device = timeline_data.get('deviceDisplayName', '') or timeline_data.get('deviceName', '')
                        # Create a deterministic hash based on name and device
                        hash_source = f"{name}:{device}"
                        if hash_source.strip(':'):
                            timeline_id = f"key_{hashlib.md5(hash_source.encode()).hexdigest()[:16]}"
                        else:
                            # Last resort - use UUID but log a warning
                            timeline_id = f"key_{uuid.uuid4().hex[:16]}"
                            _logger.warning(f"Created UUID-based timeline ID with no identifying information")

                    # Look for existing timeline - prioritize finding by timelineKey if available
                    if timeline_key:
                        timeline = self.env['manictime.user.timeline'].search([
                            ('user_id', '=', self.id),
                            ('timeline_key', '=', timeline_key)
                        ], limit=1)
                        # Fallback to timeline_id if not found by timeline_key
                        if not timeline:
                            timeline = self.env['manictime.user.timeline'].search([
                                ('user_id', '=', self.id),
                                ('timeline_id', '=', timeline_id)
                            ], limit=1)
                    else:
                        # If no timeline_key is available, search by timeline_id only
                        timeline = self.env['manictime.user.timeline'].search([
                            ('user_id', '=', self.id),
                            ('timeline_id', '=', timeline_id)
                        ], limit=1)

                    # Make sure we have the timeline_key saved correctly
                    if not timeline_key:
                        timeline_key = timeline_data.get('key', '')
                    publish_key = timeline_data.get('publishKey', '')
                    update_protocol = timeline_data.get('updateProtocol', '')
                    timestamp = timeline_data.get('timestamp', '')

                    # Extract owner information
                    owner_username = ''
                    owner_display_name = ''
                    if isinstance(timeline_data.get('owner'), dict):
                        owner = timeline_data.get('owner', {})
                        owner_username = owner.get('username', '')
                        owner_display_name = owner.get('displayName', '')

                    # Extract schema information
                    schema_info = ""
                    schema_name = ""
                    schema_version = ""
                    base_schema_name = ""
                    base_schema_version = ""
                    schema_record_id = False
                    base_schema_record_id = False

                    if isinstance(timeline_data.get('schema'), dict):
                        schema = timeline_data.get('schema', {})
                        schema_name = schema.get('name', '')
                        schema_version = schema.get('version', '')

                        # Find or create schema record
                        if schema_name and schema_version:
                            schema_record = self.env['manictime.schema'].search([
                                ('name', '=', schema_name),
                                ('version', '=', schema_version)
                            ], limit=1)

                            if not schema_record:
                                _logger.info(f"Creating new schema record: {schema_name} v{schema_version}")
                                schema_record = self.env['manictime.schema'].create({
                                    'name': schema_name,
                                    'version': schema_version
                                })

                            schema_record_id = schema_record.id

                        # Process base schema
                        base_schema = schema.get('baseSchema', {})
                        if isinstance(base_schema, dict):
                            base_schema_name = base_schema.get('name', '')
                            base_schema_version = base_schema.get('version', '')

                            # Find or create base schema record
                            if base_schema_name and base_schema_version:
                                base_schema_record = self.env['manictime.schema'].search([
                                    ('name', '=', base_schema_name),
                                    ('version', '=', base_schema_version)
                                ], limit=1)

                                if not base_schema_record:
                                    _logger.info(f"Creating new base schema record: {base_schema_name} v{base_schema_version}")
                                    base_schema_record = self.env['manictime.schema'].create({
                                        'name': base_schema_name,
                                        'version': base_schema_version
                                    })

                                base_schema_record_id = base_schema_record.id

                                # Update schema record to reference base schema
                                if schema_record_id and base_schema_record_id:
                                    self.env['manictime.schema'].browse(schema_record_id).write({
                                        'base_schema_id': base_schema_record_id
                                    })

                            # Format schema info for display
                            if base_schema_name:
                                schema_info = f"{base_schema_name} {base_schema_version}"

                        # Add schema name and version to schema info
                        if schema_name:
                            if schema_info:
                                schema_info += f" → {schema_name} {schema_version}"
                            else:
                                schema_info = f"{schema_name} {schema_version}"

                    # Extract device information
                    device_display_name = timeline_data.get('deviceDisplayName', '')
                    device_name = ''
                    environment_id_str = ''
                    environment_record_id = False

                    # Try to extract from homeEnvironment
                    if isinstance(timeline_data.get('homeEnvironment'), dict):
                        home_env = timeline_data.get('homeEnvironment', {})
                        device_name = home_env.get('deviceName', '')
                        environment_id_str = home_env.get('environmentId', '')

                        # Find or create environment record
                        if environment_id_str:
                            environment_record = self.env['manictime.environment'].search([
                                ('environment_id', '=', environment_id_str)
                            ], limit=1)

                            if not environment_record:
                                _logger.info(f"Creating new environment record: {device_name} ({environment_id_str})")
                                environment_record = self.env['manictime.environment'].create({
                                    'environment_id': environment_id_str,
                                    'device_name': device_name or device_display_name or 'Unknown Device',
                                    'device_display_name': device_display_name,
                                    'user_id': self.id
                                })

                            environment_record_id = environment_record.id

                    # Extract timeline type from schema or directly
                    timeline_type = ''
                    if schema_name:
                        if 'ComputerUsage' in schema_name:
                            timeline_type = 'Computer Usage'
                        elif 'Applications' in schema_name:
                            timeline_type = 'Applications'
                        elif 'Documents' in schema_name:
                            timeline_type = 'Documents'
                        elif 'Web' in schema_name:
                            timeline_type = 'Web'
                        elif 'Group' in schema_name or 'Generic/Group' in schema_name:
                            timeline_type = 'Group'
                        else:
                            # Extract the last part of the schema name for type
                            parts = schema_name.split('/')
                            if parts:
                                timeline_type = parts[-1]

                    if not timeline_type:
                        timeline_type = timeline_data.get('type') or timeline_data.get('timelineType', '')

                    # Set a meaningful name
                    if device_display_name:
                        timeline_name = device_display_name
                    elif device_name:
                        timeline_name = device_name
                    else:
                        timeline_name = timeline_data.get('name') or timeline_type or 'Unnamed Timeline'

                    # Extract last update time
                    last_update = None
                    if isinstance(timeline_data.get('lastUpdate'), dict):
                        last_update_data = timeline_data.get('lastUpdate', {})
                        if 'updatedUtcTime' in last_update_data:
                            try:
                                # Parse ISO format datetime
                                from datetime import datetime
                                last_update_str = last_update_data.get('updatedUtcTime', '')
                                # Remove timezone part if present (Odoo handles UTC internally)
                                if '+' in last_update_str:
                                    last_update_str = last_update_str.split('+')[0]
                                last_update = datetime.fromisoformat(last_update_str)
                            except (ValueError, TypeError):
                                _logger.warning(f"Could not parse last update time: {last_update_data.get('updatedUtcTime')}")

                    # Extract last change ID
                    last_change_id = timeline_data.get('lastChangeId', '')

                    # Extract API URLs and prepare link records
                    timeline_url = ''
                    activities_url = ''
                    changes_url = ''
                    add_changes_url = ''
                    edit_properties_url = ''
                    links_to_create = []

                    if isinstance(timeline_data.get('links'), list):
                        for link in timeline_data.get('links', []):
                            if isinstance(link, dict):
                                rel = link.get('rel', '')
                                href = link.get('href', '')

                                if not rel or not href:
                                    continue

                                # Store URLs for immediate use
                                if rel == 'self':
                                    timeline_url = href
                                elif rel == 'manictime/activities':
                                    activities_url = href
                                elif rel == 'manictime/getchanges':
                                    changes_url = href
                                elif rel == 'manictime/addchanges':
                                    add_changes_url = href
                                elif rel == 'manictime/editproperties':
                                    edit_properties_url = href

                                # Collect link data for the manictime.link model
                                # These will be created after the timeline is created or updated
                                links_to_create.append({
                                    'rel': rel,
                                    'href': href,  # Raw href from API response
                                    'pattern': None  # Will be calculated later using timeline_key
                                })

                    # Log the most important URLs to help with debugging
                    if activities_url:
                        _logger.info(f"Activities URL for timeline {timeline_id}: {activities_url}")

                    # Prepare data for update/create
                    data = {
                        'timeline_key': timeline_key,
                        'timeline_type': timeline_type,
                        'device_display_name': device_display_name,
                        'owner_username': owner_username,
                        'owner_display_name': owner_display_name,
                        'publish_key': publish_key,
                        'update_protocol': update_protocol,
                        'timestamp': timestamp,
                        'last_change_id': last_change_id,
                    }

                    # Add environment_id_str for backward compatibility
                    if environment_id_str:
                        data['environment_id_str'] = environment_id_str

                    # Add relationship fields
                    if schema_record_id:
                        data['schema_id'] = schema_record_id
                    if environment_record_id:
                        data['environment_id'] = environment_record_id

                    # Add last_update if it was successfully parsed
                    if last_update:
                        data['last_update'] = last_update

                    # Create or update the timeline
                    if timeline:
                        # Update the existing timeline
                        timeline.write(data)
                        timeline_id = timeline.id
                        result.append(timeline_id)
                    else:
                        # Get the user configuration to check for timeline default settings
                        config = self.env['manictime.config'].sudo().search([
                            ('user_id', '=', self.id)
                        ], limit=1)

                        # Use the config default if available, otherwise default to True (opt-out)
                        # More reliable to use the config model directly
                        default_selected = config.sync_by_default if config else True

                        data.update({
                            'user_id': self.id,
                            'timeline_id': timeline_id,  # Legacy field
                            'is_selected': default_selected,
                        })

                        new_timeline = self.env['manictime.user.timeline'].create(data)
                        timeline_id = new_timeline.id
                        result.append(timeline_id)

                    # Process capabilities after the timeline is available
                    if links_to_create:
                        # First, get the timeline object
                        timeline_obj = self.env['manictime.user.timeline'].browse(timeline_id)

                        # Disconnect from all existing links
                        if timeline_obj.link_ids:
                            timeline_obj.write({'link_ids': [(5, 0, 0)]})  # Clear all links

                        # Process each link capability
                        for link_data in links_to_create:
                            try:
                                rel = link_data['rel']
                                href = link_data['href']

                                if not rel or not href:
                                    continue

                                # Extract a pattern from the URL by replacing the timeline key with a placeholder
                                # Using the Link model's helper method for consistency
                                pattern = self.env['manictime.link'].extract_url_pattern(href, timeline_obj.timeline_key)

                                # Look for an existing capability with this rel and pattern
                                existing_link = self.env['manictime.link'].search([
                                    ('rel', '=', rel),
                                    ('pattern', '=', pattern)
                                ], limit=1)

                                if existing_link:
                                    # Add this timeline to the existing capability
                                    existing_link.write({
                                        'timeline_ids': [(4, timeline_id)]
                                    })
                                else:
                                    # Create a new capability and link it to this timeline
                                    new_link = self.env['manictime.link'].create({
                                        'rel': rel,
                                        'pattern': pattern,
                                        'timeline_ids': [(4, timeline_id)]
                                    })
                                    _logger.info(f"Created new API capability: {rel} with pattern {pattern}")
                            except Exception as link_error:
                                _logger.warning(f"Failed to process capability {link_data.get('rel', 'unknown')} for timeline {timeline_id}: {str(link_error)}")

                except Exception as timeline_error:
                    _logger.error(f"Error processing timeline: {str(timeline_error)}")
                    # Continue with other timelines, don't let one failure abort all
                    continue

            return result

        except Exception as e:
            _logger.error(f"Error fetching or storing timelines: {str(e)}")
            return []

    def manictime_sync_all_tags(self):
        """Sync ALL tag combinations from ManicTime (admin only)"""
        self.ensure_one()

        if not self.manictime_enabled:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('ManicTime integration is not enabled for this user.'),
                    'type': 'danger',
                }
            }

        # Check if user is a ManicTime manager
        if not self.env.user.has_group('manictime_server.group_manictime_manager'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Only ManicTime managers can sync all tags.'),
                    'type': 'danger',
                }
            }

        if not self._check_manictime_auth():
            return self._manictime_auth_expired_notification()

        # Create a savepoint to roll back to if something goes wrong
        savepoint_name = f"manictime_sync_tags_{self.id}_{int(datetime.now().timestamp())}"
        self.env.cr.execute(f"SAVEPOINT {savepoint_name}")

        try:
            # Import ManicTime client libraries
            import sys
            import os
            server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            manictime_path = os.path.join(server_path, 'manictime')
            if manictime_path not in sys.path:
                sys.path.append(manictime_path)

            # Now import from manictime library
            from client import ManicTimeClient, CachedManicTimeClient
            from configuration import Config

            # Get the stored secret or use token
            secret = self._get_manictime_secret()
            server_url = self.get_manictime_server_url()

            if self.manictime_auth_type == 'bearer':
                # Get the access token from secure storage
                access_token = self.env['manictime.token.storage'].get_secret(self.id, 'access_token')

                config = Config(
                    server_url=server_url,
                    auth_type=self.manictime_auth_type,
                    token=access_token,
                    timeout=30
                )
            else:  # ntlm
                config = Config(
                    server_url=server_url,
                    auth_type=self.manictime_auth_type,
                    username=self.manictime_client_id_username,
                    password=secret,
                    timeout=30
                )

            # Use cached client for better performance
            client = CachedManicTimeClient(config)

            _logger.info("Fetching all tag combinations including team and user data")

            try:
                # Use the UI API endpoint that returns actual tag data
                url = f"{client.config.server_url}/ui-api/analytics/timelines/tagEditorTags"
                headers = {"Accept": "application/json"}
                
                _logger.info(f"Fetching all tags from UI API endpoint: {url}")
                tag_combinations_response = client._make_request(url, headers=headers)
                
                # Fall back to legacy endpoint if UI API returns empty results
                if isinstance(tag_combinations_response, dict) and 'tagCombinations' in tag_combinations_response:
                    if not tag_combinations_response.get('tagCombinations'):
                        _logger.warning("UI API returned empty tagCombinations list, falling back to legacy endpoint")
                        # Fall back to legacy endpoint
                        url = f"{client.config.server_url}/api/tagcombinationlist?getAll=true"
                        headers = {"Accept": "application/vnd.manictime.v3+json"}
                        tag_combinations_response = client._make_request(url, headers=headers)
                
                tag_combinations = self._sync_manictime_tags(client, force_response=tag_combinations_response)

                # Show success notification
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Tags Synchronized'),
                        'message': _('Successfully synchronized %s tag combinations from all users and teams.') % len(tag_combinations),
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

            except Exception as tag_error:
                _logger.error(f"Error syncing all tags: {str(tag_error)}")
                # Roll back to savepoint
                self.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Failed to sync all tags: %s') % str(tag_error),
                        'type': 'danger',
                    }
                }

        except Exception as e:
            _logger.error(f"Error syncing all tags: {str(e)}")
            # Roll back to savepoint
            self.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Unexpected error when syncing all tags: %s') % str(e),
                    'type': 'danger',
                }
            }

    def manictime_sync_data(self):
        """Sync all ManicTime data - timelines, tags, and activities"""
        from datetime import datetime, timedelta
        
        self.ensure_one()

        if not self.manictime_enabled:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('ManicTime integration is not enabled for this user.'),
                    'type': 'danger',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                        'infos': {'effect': {'type': 'reload'}}
                    }
                }
            }

        if not self._check_manictime_auth():
            return self._manictime_auth_expired_notification()

        # Check if sync start date is provided in context (for incremental syncs)
        if self.env.context.get('sync_since'):
            sync_start = self.env.context.get('sync_since')
            _logger.info(f"Using provided sync start date from context: {sync_start}")
        else:
            # Get configured sync interval from settings
            if self.env.context.get('from_cron', False):
                # For cron job execution, cap at 7 days max to avoid timeouts on initial sync
                # For subsequent syncs, we'll use the last_sync time via sync_since parameter
                sync_days = 7  # Cap at 7 days for Odoo.sh compatibility 
                _logger.info(f"Using capped sync interval ({sync_days} days) for cron job execution")
            else:
                # For manual syncs, use the configured interval (default 7 days)
                sync_days = int(self.env['ir.config_parameter'].sudo().get_param(
                    'manictime_server.sync_interval', default='7'))
                
                # Safety cap at 7 days to avoid timeouts
                if sync_days > 7:
                    _logger.warning(f"Configured sync interval ({sync_days} days) exceeds recommended maximum (7 days). Capping at 7 days.")
                    sync_days = 7

            # Calculate sync start time (X days ago, max 7 days)
            sync_start = datetime.now() - timedelta(days=sync_days)
            _logger.info(f"Syncing data from {sync_start} ({sync_days} days back)")

        # Create a savepoint to roll back to if something goes wrong
        savepoint_name = f"manictime_sync_{self.id}_{int(datetime.now().timestamp())}"
        self.env.cr.execute(f"SAVEPOINT {savepoint_name}")

        timelines_count = 0
        tag_combinations_count = 0
        total_activities = 0

        try:
            # Import ManicTime client libraries
            import sys
            import os
            # Add the path to the manictime library
            server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            manictime_path = os.path.join(server_path, 'manictime')
            if manictime_path not in sys.path:
                sys.path.append(manictime_path)

            # Now import from manictime library
            from client import ManicTimeClient, CachedManicTimeClient
            from configuration import Config
            from models import Activity, TagCombination

            # Get the stored secret or use token
            secret = self._get_manictime_secret()
            server_url = self.get_manictime_server_url()

            if self.manictime_auth_type == 'bearer':
                # Get the access token from secure storage
                access_token = self.env['manictime.token.storage'].get_secret(self.id, 'access_token')

                config = Config(
                    server_url=server_url,
                    auth_type=self.manictime_auth_type,
                    token=access_token,
                    timeout=30
                )
            else:  # ntlm
                config = Config(
                    server_url=server_url,
                    auth_type=self.manictime_auth_type,
                    username=self.manictime_client_id_username,
                    password=secret,
                    timeout=30
                )

            # Use cached client for better performance
            client = CachedManicTimeClient(config)

            # Check if a specific timeline is specified in context
            active_timeline_id = self.env.context.get('active_timeline_id', False)

            # Always sync tags first regardless of whether we're syncing a specific timeline
            _logger.info("Fetching tag combinations")
            try:
                # Start a new savepoint for tag sync
                self.env.cr.execute("SAVEPOINT tag_sync")

                tag_combinations = self._sync_manictime_tags(client)
                tag_combinations_count = len(tag_combinations)
                _logger.info(f"Synced {tag_combinations_count} tag combinations")

                # Release the savepoint if successful
                self.env.cr.execute("RELEASE SAVEPOINT tag_sync")
            except Exception as tag_error:
                _logger.error(f"Error syncing tag combinations: {str(tag_error)}")
                tag_combinations_count = 0
                # Roll back to savepoint
                self.env.cr.execute("ROLLBACK TO SAVEPOINT tag_sync")
                # Continue with timeline sync even if tag sync fails

            if not active_timeline_id:
                # Sync all timelines (only if not syncing a specific timeline)
                _logger.info("Fetching all available timelines")
                try:
                    # Start a new savepoint for timeline sync
                    self.env.cr.execute("SAVEPOINT timeline_sync")

                    timelines = self._fetch_manictime_timelines(client)
                    timelines_count = len(timelines)
                    _logger.info(f"Found {timelines_count} timelines")

                    # Release the savepoint if successful
                    self.env.cr.execute("RELEASE SAVEPOINT timeline_sync")
                except Exception as timeline_error:
                    _logger.error(f"Error syncing timelines: {str(timeline_error)}")
                    # Roll back to savepoint
                    self.env.cr.execute("ROLLBACK TO SAVEPOINT timeline_sync")
                    # Continue with activities sync

            # 3. Sync activities for the selected timeline(s)
            if active_timeline_id:
                # If a specific timeline was requested, only sync that one
                timelines_to_sync = self.env['manictime.user.timeline'].browse(active_timeline_id)
                single_timeline = True
            else:
                # Otherwise get all timelines (not just selected ones)
                timelines_to_sync = self.manictime_timeline_ids
                single_timeline = False

            # Sync each timeline
            for timeline in timelines_to_sync:
                try:
                    # Start a new savepoint for each timeline's activities sync
                    savepoint_timeline = f"timeline_activities_{timeline.id}"
                    self.env.cr.execute(f"SAVEPOINT {savepoint_timeline}")

                    _logger.info(f"Syncing timeline {timeline.name} from {sync_start}")

                    # Use timeline_key as the primary identifier for API calls
                    # This is more reliable and consistent with the API
                    timeline_identifier = timeline.timeline_key

                    # If timeline_key is not available (old records), fall back to timeline_id
                    if not timeline_identifier:
                        timeline_identifier = timeline.timeline_id
                        _logger.warning(f"Using legacy timeline_id for timeline {timeline.name} - update recommended")

                    # Get the activities URL from the link model
                    activities_url = timeline.get_activities_url()

                    # Add detailed logging about the timeline and its links
                    _logger.info(f"Timeline {timeline.name} (ID: {timeline.id}):")
                    _logger.info(f"  - timeline_key: {timeline.timeline_key}")
                    _logger.info(f"  - timeline_id (legacy): {timeline.timeline_id}")
                    _logger.info(f"  - schema: {timeline.schema_id.name if timeline.schema_id else 'None'}")
                    _logger.info(f"  - environment: {timeline.environment_id.device_name if timeline.environment_id else 'None'}")
                    _logger.info(f"  - link count: {len(timeline.link_ids)}")

                    # Log the available links
                    if timeline.link_ids:
                        _logger.info("Available links:")
                        for link in timeline.link_ids:
                            formatted_url = timeline.get_link_url(link.rel)
                            _logger.info(f"  - {link.rel}: {formatted_url} (pattern: {link.pattern})")

                    _logger.info(f"Getting activities for timeline {timeline.name} using identifier {timeline_identifier} with URL {activities_url}")

                    # Call the API to get activities for the given date range
                    # Check if the client supports the activities_url parameter
                    try:
                        # First try with the activities_url parameter
                        activities = client.get_activities_for_date_range(
                            timeline_identifier,
                            sync_start,
                            datetime.now(),
                            activities_url=activities_url
                        )
                    except TypeError as e:
                        if "unexpected keyword argument 'activities_url'" in str(e):
                            # If the client doesn't support the parameter, call without it
                            _logger.info(f"Client doesn't support activities_url parameter, using default URL")
                            activities = client.get_activities_for_date_range(
                                timeline_identifier,
                                sync_start,
                                datetime.now()
                            )
                        else:
                            # Re-raise any other TypeError
                            raise
                    
                    # Handle raw API response that might need additional processing
                    if isinstance(activities, list) and activities and isinstance(activities[0], dict):
                        # This is likely raw API response format from the JSON rather than Activity objects
                        _logger.info(f"Converting raw activity data to Activity objects")
                        
                        # Import the Activity model for conversion
                        try:
                            import sys, os
                            server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            manictime_path = os.path.join(server_path, 'manictime')
                            if manictime_path not in sys.path:
                                sys.path.append(manictime_path)
                            from models import Activity
                            
                            # Convert raw dictionary data to Activity objects
                            processed_activities = []
                            for act_data in activities:
                                # Check if we're dealing with the expected format
                                if 'entityId' in act_data and 'values' in act_data:
                                    try:
                                        entity_id = act_data.get('entityId')
                                        values = act_data.get('values', {})
                                        
                                        # Extract time interval info
                                        time_interval = values.get('timeInterval', {})
                                        start_time = None
                                        end_time = None
                                        
                                        if time_interval:
                                            start_str = time_interval.get('start')
                                            duration = time_interval.get('duration', 0)
                                            
                                            if start_str:
                                                # Parse start time, possibly with timezone
                                                try:
                                                    # Try to parse ISO format datetime
                                                    from datetime import datetime, timedelta
                                                    
                                                    # Remove timezone part if present for parsing
                                                    if '+' in start_str or ('-' in start_str and 'T' in start_str):
                                                        import re
                                                        match = re.match(r'(.+)(?:[+-][\d:]+)$', start_str)
                                                        if match:
                                                            start_str = match.group(1)
                                                    
                                                    # Parse the datetime
                                                    if 'T' in start_str:
                                                        start_time = datetime.fromisoformat(start_str.replace('T', ' '))
                                                    else:
                                                        start_time = datetime.fromisoformat(start_str)
                                                    
                                                    # Calculate end time from duration (in seconds)
                                                    if duration:
                                                        end_time = start_time + timedelta(seconds=duration)
                                                    else:
                                                        end_time = start_time + timedelta(minutes=1)  # Default to 1 minute
                                                except Exception as dt_error:
                                                    _logger.warning(f"Error parsing activity time: {str(dt_error)}")
                                                    # Skip this activity if we can't parse the times
                                                    continue
                                        
                                        # Create an Activity object
                                        activity_obj = Activity(
                                            id=entity_id,
                                            title=values.get('name', 'Untitled'),
                                            start=start_time,
                                            end=end_time,
                                            application=values.get('application', ''),
                                            notes=values.get('notes', '')
                                        )
                                        
                                        # Add to our list
                                        processed_activities.append(activity_obj)
                                    except Exception as conv_error:
                                        _logger.warning(f"Error converting activity {act_data.get('entityId')}: {str(conv_error)}")
                                        continue
                            
                            if processed_activities:
                                _logger.info(f"Converted {len(processed_activities)} raw activities to Activity objects")
                                activities = processed_activities
                        except ImportError:
                            _logger.warning("Failed to import Activity model, using raw data")
                            # Continue with raw data, our processing method will handle it

                    _logger.info(f"Retrieved {len(activities)} activities for timeline {timeline.name}")

                    # Sync happens in a context that won't trigger validation errors
                    sync_context = {'calling_method': 'manictime_sync'}

                    # Process activities in smaller batches to avoid large transactions
                    batch_size = 100
                    for i in range(0, len(activities), batch_size):
                        batch = activities[i:i+batch_size]

                        # Create a savepoint for the batch
                        batch_savepoint = f"activities_batch_{i}"
                        self.env.cr.execute(f"SAVEPOINT {batch_savepoint}")

                        try:
                            # Process the batch
                            for activity in batch:
                                self.with_context(sync_context).sudo()._create_or_update_activity_from_object(timeline, activity)

                            # Commit the batch
                            self.env.cr.execute(f"RELEASE SAVEPOINT {batch_savepoint}")
                        except Exception as batch_error:
                            _logger.error(f"Error syncing batch of activities (offset {i}): {str(batch_error)}")
                            # Roll back the batch
                            self.env.cr.execute(f"ROLLBACK TO SAVEPOINT {batch_savepoint}")

                    # Update last sync time - in a separate transaction
                    timeline.write({
                        'last_sync': datetime.now(),
                    })

                    total_activities += len(activities)

                    # Release the savepoint for this timeline
                    self.env.cr.execute(f"RELEASE SAVEPOINT {savepoint_timeline}")

                except Exception as timeline_error:
                    _logger.error(f"Error syncing timeline {timeline.name}: {str(timeline_error)}")
                    # Roll back to the timeline savepoint
                    self.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_timeline}")
                    # Continue with other timelines even if one fails

            # Update last sync time for the user - in a separate transaction to avoid rollbacks
            # affecting this important information
            try:
                # Update the config model directly
                config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)
                if config:
                    config.write({'last_sync': datetime.now()})
            except Exception as write_error:
                _logger.error(f"Error updating last sync time: {str(write_error)}")

            # Release the main savepoint if everything succeeded
            self.env.cr.execute(f"RELEASE SAVEPOINT {savepoint_name}")

            # Return a success notification with reload
            if single_timeline:
                # Single timeline sync success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Timeline Sync Complete'),
                        'message': _('Successfully synced %s activities for timeline "%s"') %
                                     (total_activities, timeline.name),
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }
            else:
                # Full sync success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Complete'),
                        'message': _('Successfully synced %s timelines, %s tag combinations, and %s activities') %
                                     (timelines_count, tag_combinations_count, total_activities),
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window_close',
                            'infos': {'effect': {'type': 'reload'}}
                        }
                    }
                }

        except Exception as e:
            _logger.error(f"Error syncing ManicTime data: {str(e)}")

            # Roll back to main savepoint
            self.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")

            # Show error notification with reload
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': _('Failed to sync ManicTime data: %s') % str(e),
                    'type': 'danger',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                        'infos': {'effect': {'type': 'reload'}}
                    }
                }
            }

    def manictime_sync_activities(self):
        """Legacy method, redirects to manictime_sync_data"""
        return self.manictime_sync_data()

    def _check_manictime_auth(self):
        """Check if authentication is valid and try to refresh if needed"""
        self.ensure_one()

        # Get the user's ManicTime config
        config = self.env['manictime.config'].sudo().search([('user_id', '=', self.id)], limit=1)

        if not config:
            return False

        # First check if we have a valid token based on expiry dates
        valid_token = False

        if config.auth_type == 'bearer':
            # Check if we have the access token in secure storage
            access_token = self.env['manictime.token.storage'].get_secret(self.id, 'access_token')
            if access_token and config.token_expiry and config.token_expiry >= datetime.now():
                valid_token = True

        elif config.auth_type == 'ntlm':
            # For NTLM, we just use the expiry date as validation
            if config.token_expiry and config.token_expiry >= datetime.now():
                valid_token = True

        # If token is invalid, check if we should try automatic reauthentication
        if not valid_token:
            # Check if auto reauthentication is enabled for this user
            if config.auto_reauth and self._get_manictime_secret():
                # We have credentials and auto reauth is enabled, try to refresh
                try:
                    _logger.info(f"Attempting auto-reauthentication for user {self.name}")
                    self.with_context(suppress_notifications=True).manictime_authenticate()

                    # Recheck auth after attempted refresh
                    if config.token_expiry and config.token_expiry >= datetime.now():
                        _logger.info(f"Auto-reauthentication successful for user {self.name}")
                        return True
                    else:
                        _logger.warning(f"Auto-reauthentication failed for user {self.name}")
                        return False

                except Exception as e:
                    _logger.error(f"Error during auto-reauthentication for user {self.name}: {str(e)}")
                    return False

            return False

        return True

    def _manictime_auth_expired_notification(self):
        """Return authentication required notification"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Authentication Required'),
                'message': _('Please authenticate with ManicTime server first'),
                'type': 'warning',
                'next': {
                    'type': 'ir.actions.act_window_close',
                    'infos': {'effect': {'type': 'reload'}}
                }
            }
        }

    def _sync_manictime_tags(self, client, force_response=None):
        """Sync tag combinations from ManicTime server

        Args:
            client: ManicTime client instance
            force_response: Optional pre-fetched tag combinations response
                           (useful for cases where we need to use custom parameters)

        Returns:
            List of tag combination IDs that were created or updated
        """
        self.ensure_one()

        try:
            # Use pre-fetched response if provided
            if force_response is not None:
                _logger.info("Using pre-fetched tag combinations response")
                tag_combinations_response = force_response
            else:
                # Get tag combinations from ManicTime
                # Check if user is a ManicTime manager - if so, try to get all tags
                is_manager = self.env.user.has_group('manictime_server.group_manictime_manager')

                # Use the new UI API endpoint that returns actual tag data
                url = f"{client.config.server_url}/ui-api/analytics/timelines/tagEditorTags"
                headers = {"Accept": "application/json"}
                
                try:
                    _logger.info(f"Fetching tags from new UI API endpoint: {url}")
                    tag_combinations_response = client._make_request(url, headers=headers)
                except Exception as e:
                    _logger.warning(f"Failed to get tags from UI API endpoint: {str(e)}. Falling back to legacy endpoint.")
                    # Fall back to legacy endpoint if UI API fails
                    if is_manager:
                        # Manager can try to get all tags
                        url = f"{client.config.server_url}/api/tagcombinationlist?getAll=true"
                        headers = {"Accept": "application/vnd.manictime.v3+json"}
                        try:
                            _logger.info(f"Falling back to legacy endpoint with getAll=true: {url}")
                            tag_combinations_response = client._make_request(url, headers=headers)
                        except Exception as e2:
                            _logger.warning(f"Failed to get all tags from legacy endpoint: {str(e2)}. Trying without getAll parameter.")
                            # Try once more without getAll parameter
                            url = f"{client.config.server_url}/api/tagcombinationlist"
                            tag_combinations_response = client._make_request(url, headers=headers)
                    else:
                        # Regular user gets only their own tags
                        url = f"{client.config.server_url}/api/tagcombinationlist"
                        headers = {"Accept": "application/vnd.manictime.v3+json"}
                        _logger.info(f"Falling back to legacy endpoint: {url}")
                        tag_combinations_response = client._make_request(url, headers=headers)

            # Verify response format and extract tag combinations
            tag_combinations = []
            
            if not isinstance(tag_combinations_response, list):
                _logger.info(f"Processing dictionary-style tag combinations response")
                if isinstance(tag_combinations_response, dict):
                    # First check for the UI API format with both tagCombinations and tags
                    if 'tagCombinations' in tag_combinations_response and isinstance(tag_combinations_response['tagCombinations'], list):
                        ui_api_tag_combinations = tag_combinations_response.get('tagCombinations', [])
                        _logger.info(f"Found UI API 'tagCombinations' key with {len(ui_api_tag_combinations)} items")
                        
                        # Process the new format from /ui-api/analytics/timelines/tagEditorTags
                        for tag_combo_data in ui_api_tag_combinations:
                            if isinstance(tag_combo_data, dict) and 'tag' in tag_combo_data:
                                tag_data = tag_combo_data.get('tag', {})
                                
                                # Check if it has the required fields
                                if tag_data.get('key') and tag_data.get('tagCombination'):
                                    # Create a standardized format for processing
                                    processed_tag = {
                                        'id': tag_data.get('key'),  # Use key as ID
                                        'name': tag_data.get('tagCombination', ''),
                                        'tags': [tag_data.get('tagCombination', '')],  # Use tagCombination as the tag
                                        'color': tag_data.get('color', ''),
                                        'description': '',  # No description in this format
                                        'isBillable': tag_data.get('isBillable', False)
                                    }
                                    tag_combinations.append(processed_tag)
                    
                    # If we got tags from UI API, we're done
                    if tag_combinations:
                        _logger.info(f"Successfully processed {len(tag_combinations)} tags from UI API format")
                    # If not, try the other formats
                    else:
                        # Process ManicTime API v3 format that returns {"tagCombinations": [...]}
                        if 'tagCombinations' in tag_combinations_response:
                            tag_combinations = tag_combinations_response.get('tagCombinations', [])
                            _logger.info(f"Found regular API 'tagCombinations' key with {len(tag_combinations)} items")
                        # Try other common formats
                        elif 'tags' in tag_combinations_response:
                            tag_combinations = tag_combinations_response.get('tags', [])
                            _logger.info(f"Found 'tags' key with {len(tag_combinations)} items")
                        elif 'combinations' in tag_combinations_response:
                            tag_combinations = tag_combinations_response.get('combinations', [])
                            _logger.info(f"Found 'combinations' key with {len(tag_combinations)} items")
                        else:
                            # Look for any list in the response
                            list_keys = [k for k, v in tag_combinations_response.items() if isinstance(v, list)]
                            if list_keys:
                                first_list_key = list_keys[0]
                                tag_combinations = tag_combinations_response.get(first_list_key, [])
                                _logger.info(f"Found list under key '{first_list_key}' with {len(tag_combinations)} items")
                            else:
                                _logger.error("Could not extract tag combinations from response")
                                _logger.error(f"Response keys: {list(tag_combinations_response.keys())}")
                                return []
                else:
                    _logger.error(f"Unexpected response type: {type(tag_combinations_response)}")
                    return []
            else:
                # Response is already a list
                tag_combinations = tag_combinations_response

            _logger.info(f"Retrieved {len(tag_combinations)} tag combinations from ManicTime")

            # Import necessary for TagCombination model
            try:
                import sys, os
                server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manictime_path = os.path.join(server_path, 'manictime')
                if manictime_path not in sys.path:
                    sys.path.append(manictime_path)
                from models import TagCombination
            except ImportError as e:
                _logger.error(f"Could not import TagCombination model: {str(e)}")
                # Continue with original implementation if import fails

            # Sync happens in a context that won't trigger validation errors
            sync_context = {'calling_method': 'manictime_sync'}

            result = []

            # Create or update tag combinations
            for tag_data in tag_combinations:
                try:
                    # Try to use TagCombination model for robust parsing
                    if 'TagCombination' in locals():
                        tag_obj = TagCombination.from_dict(tag_data)
                        name = tag_obj.name
                        tags = tag_obj.tags
                        description = tag_obj.description or ''
                        color = tag_obj.color or ''
                    else:
                        # Fall back to manual parsing
                        # Check if tag_data is a dictionary, convert if not
                        if not isinstance(tag_data, dict):
                            if isinstance(tag_data, str):
                                # Simple string tag
                                tag_data = {'name': tag_data, 'tags': [tag_data]}
                            else:
                                _logger.warning(f"Unexpected tag combination format: {type(tag_data)}, skipping.")
                                continue

                        name = tag_data.get('name', 'Unnamed Tag')

                        # Get tags from the combination - ensure it's a list
                        tags = tag_data.get('tags', [])
                        if not isinstance(tags, list):
                            tags = [str(tags)] if tags else []

                        description = tag_data.get('description', '')
                        color = tag_data.get('color', '')

                    # Get the ID from the tag combination
                    external_id = str(tag_data.get('id') or tag_data.get('tagId', ''))
                    if not external_id:
                        _logger.warning(f"Tag combination missing ID, generating a random one")
                        external_id = f"generated_{uuid.uuid4()}"

                    # Create tags string
                    tags_string = ','.join(tags) if tags else ''

                    # Look for existing record
                    tag_record = self.env['manictime.tag.combination'].search([
                        ('user_id', '=', self.id),
                        ('entity_id', '=', external_id)
                    ], limit=1)

                    if tag_record:
                        # Update existing record
                        # Get billable status if available
                        is_billable = False
                        if isinstance(tag_data, dict):
                            is_billable = tag_data.get('isBillable', False)
                        
                        tag_record.with_context(sync_context).write({
                            'name': name,
                            'tags': tags_string,
                            'description': description,
                            'color': color,
                            'is_billable': is_billable
                        })
                        result.append(tag_record.id)
                    else:
                        # Get billable status if available
                        is_billable = False
                        if isinstance(tag_data, dict):
                            is_billable = tag_data.get('isBillable', False)
                            
                        # Create new record
                        new_tag = self.env['manictime.tag.combination'].with_context(sync_context).create({
                            'user_id': self.id,
                            'entity_id': external_id,
                            'name': name,
                            'tags': tags_string,
                            'description': description,
                            'color': color,
                            'is_billable': is_billable
                        })
                        result.append(new_tag.id)
                except Exception as tag_error:
                    _logger.error(f"Error processing tag combination: {str(tag_error)}")
                    # Continue with other tag combinations

            # Log success
            _logger.info(f"Successfully synchronized {len(result)} tag combinations")
            return result

        except Exception as e:
            _logger.error(f"Error syncing tag combinations: {str(e)}")
            return []

    def _create_or_update_activity_from_object(self, timeline, activity):
        """Create or update an activity record from Activity object"""
        try:
            # Validate activity object to ensure it has necessary attributes
            if not hasattr(activity, 'id') or not activity.id:
                # Log more details to help diagnose the issue
                _logger.warning(f"Activity missing ID, skipping. Activity attrs: {dir(activity)}")
                if hasattr(activity, '__dict__'):
                    _logger.warning(f"Activity dict content: {activity.__dict__}")
                return

            if not hasattr(activity, 'start') or not hasattr(activity, 'end'):
                _logger.warning(f"Activity {activity.id} missing start/end time, skipping")
                return

            # Find existing activity
            activity_record = self.env['manictime.activity'].sudo().search([
                ('user_id', '=', self.id),
                ('timeline_id', '=', timeline.id),
                ('entity_id', '=', activity.id),
            ], limit=1)

            # Process tags
            activity_tags = []
            if hasattr(activity, 'tags'):
                if isinstance(activity.tags, list):
                    activity_tags = activity.tags
                elif isinstance(activity.tags, str):
                    # Split string by commas if it's a string
                    activity_tags = [tag.strip() for tag in activity.tags.split(',') if tag.strip()]
                else:
                    # For any other type, try to convert to string
                    activity_tags = [str(activity.tags)]

            # Create a clean, comma-separated string of tags
            tags_string = ','.join(tag for tag in activity_tags if tag)

            # Create a better title if needed
            title = getattr(activity, 'title', '') or 'Untitled'
            application = getattr(activity, 'application', '') or ''

            # Add application to title if it's not already included
            if application and application not in title:
                title = f"{application} - {title}"

            # Process start and end times - handle timezone information
            from datetime import datetime
            import pytz
            import re
            
            start_time = activity.start
            end_time = activity.end
            
            # Helper function to convert tzinfo-aware datetime to naive UTC
            def make_naive_datetime(dt):
                if not dt:
                    return dt
                    
                if isinstance(dt, str):
                    # Check if it's a timezone-aware ISO string (e.g., "2024-09-02T07:52:30-04:00")
                    if ('+' in dt or '-' in dt and 'T' in dt) or 'Z' in dt:
                        try:
                            # First, extract the datetime part without timezone to parse it
                            match = re.match(r'(.+?)(?:[+-][\d:]+|Z)$', dt)
                            if match:
                                dt_part = match.group(1)
                                # Parse as datetime - handle T separator
                                if 'T' in dt_part:
                                    dt_part = dt_part.replace('T', ' ')
                                return datetime.fromisoformat(dt_part)
                        except Exception as e:
                            _logger.warning(f"Failed to parse timezone string {dt}: {str(e)}")
                            return dt
                    return dt
                
                # For datetime objects with tzinfo
                if hasattr(dt, 'tzinfo') and dt.tzinfo:
                    try:
                        # Convert to UTC and remove timezone info
                        if hasattr(pytz, 'UTC'):
                            # Using pytz if available (Odoo standard way)
                            utc_dt = dt.astimezone(pytz.UTC)
                            return utc_dt.replace(tzinfo=None)
                        else:
                            # Fallback to standard datetime
                            utc_dt = dt.astimezone(datetime.timezone.utc)
                            return utc_dt.replace(tzinfo=None)
                    except Exception as e:
                        _logger.warning(f"Error converting datetime timezone: {str(e)}")
                
                return dt
            
            # Convert times to naive UTC
            start_time = make_naive_datetime(start_time)
            end_time = make_naive_datetime(end_time)
            
            # Prepare activity data
            activity_data = {
                'user_id': self.id,
                'timeline_id': timeline.id,
                'entity_id': activity.id,
                'name': title,
                'start_time': start_time,
                'end_time': end_time,
                'application': application,
                'tags': tags_string,
                'notes': getattr(activity, 'notes', '') or ''
            }

            # Ensure context for preventing validation errors
            sync_context = {'calling_method': 'manictime_sync'}

            if activity_record:
                # Update existing record
                activity_record.sudo().with_context(**sync_context).write(activity_data)
            else:
                # Create new record
                self.env['manictime.activity'].sudo().with_context(**sync_context).create(activity_data)

        except Exception as e:
            _logger.error(f"Error creating/updating activity {getattr(activity, 'id', 'unknown')}: {str(e)}")
            # Continue with other activities

    @api.model_create_multi
    def create(self, vals_list):
        """Extend create to ensure ManicTime configuration is created if needed"""
        users = super(ResUsers, self).create(vals_list)

        # Create manictime.config entries for users that need it
        for user in users:
            # Skip for portal/public users
            if user.has_group('base.group_user') and not self.env['manictime.config'].search_count([('user_id', '=', user.id)]):
                # Create default config
                config_vals = {
                    'user_id': user.id,
                    'enabled': False,
                    'auth_type': self.env['ir.config_parameter'].sudo().get_param(
                        'manictime_server.auth_type', default='bearer'),
                    'sync_by_default': True,
                    'auto_reauth': True,
                }
                self.env['manictime.config'].sudo().create(config_vals)

        return users

    @api.model
    def cron_sync_manictime_activities(self):
        """Cron job method to sync ManicTime data for all active users
        
        This method implements idempotent sync strategies:
        1. For initial sync: Cap at configured interval (max 7 days from current date)
        2. For subsequent syncs: Only sync since the last successful sync
        """
        from datetime import timedelta
        
        # Find all users with valid ManicTime authentication based on config
        configs = self.env['manictime.config'].search([
            ('token_expiry', '>', fields.Datetime.now())
        ])
        users = self.browse([config.user_id.id for config in configs])

        for user in users:
            try:
                # Get user's configuration
                config = self.env['manictime.config'].sudo().search([('user_id', '=', user.id)], limit=1)
                if not config:
                    _logger.warning(f"No ManicTime configuration found for user {user.name}, skipping sync")
                    continue
                
                # Check if this is an initial sync or subsequent sync
                if config.last_sync:
                    # Subsequent sync: Use the last sync time as the start date
                    _logger.info(f"Performing incremental sync for user {user.name} since {config.last_sync}")
                    # Add a small buffer (1 hour) to catch any activities that might have been missed
                    sync_since = config.last_sync - timedelta(hours=1)
                    user.with_user(user).with_context(from_cron=True, sync_since=sync_since).manictime_sync_data()
                else:
                    # Initial sync: Cap at max 7 days from current date 
                    _logger.info(f"Performing initial sync for user {user.name} (capped at 7 days)")
                    # We use from_cron=True which already limits the sync to proper intervals
                    user.with_user(user).with_context(from_cron=True).manictime_sync_data()

            except Exception as e:
                _logger.error(f"Error syncing ManicTime for user {user.name}: {str(e)}")
                continue

        return True
