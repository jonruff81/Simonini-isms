"""
Phase Specs API endpoints
Fetches PDF files from JobTread Phase Specs job (RES-02)
"""
import logging
from flask import Blueprint, jsonify, g
from app.utils.auth import require_auth, html_require_auth
from app.config import PHASE_SPECS_JOB_ID
from app.jobtread_pave_client import JobTreadPaveClient, JobTreadAPIError

logger = logging.getLogger(__name__)

phase_specs_bp = Blueprint('phase_specs', __name__, url_prefix='/api/phase-specs')


@phase_specs_bp.route('', methods=['GET'])
@require_auth
def get_phase_specs():
    """
    Get all Phase Spec PDF files from JobTread

    Returns:
        JSON list of phase spec files with id, name, url, size, type
    """
    try:
        client = JobTreadPaveClient()
        files = client.get_phase_spec_files(PHASE_SPECS_JOB_ID)

        # Format response
        result = []
        for f in files:
            # Extract phase code from filename (e.g., "Phase 30-500 ALARM SYSTEM.pdf" -> "30-500")
            import re
            name = f.get('name', '')
            match = re.search(r'Phase\s+(\d+-\d+)', name)
            phase_code = match.group(1) if match else None

            # Extract description (text after phase code, before .pdf)
            desc_match = re.search(r'Phase\s+\d+-\d+\s+(.+?)\.pdf', name, re.IGNORECASE)
            description = desc_match.group(1) if desc_match else name.replace('.pdf', '')

            result.append({
                'id': f.get('id'),
                'name': f.get('name'),
                'phase_code': phase_code,
                'description': description,
                'url': f.get('url'),
                'size': f.get('size'),
                'size_kb': round(f.get('size', 0) / 1024, 1),
                'type': f.get('type'),
                'created_at': f.get('createdAt')
            })

        return jsonify({
            'success': True,
            'count': len(result),
            'files': result
        })

    except JobTreadAPIError as e:
        logger.error(f"JobTread API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error fetching phase specs: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch phase specs'
        }), 500


@phase_specs_bp.route('/<file_id>', methods=['GET'])
@require_auth
def get_phase_spec_file(file_id: str):
    """
    Get a single Phase Spec file by ID

    Args:
        file_id: JobTread file ID

    Returns:
        JSON with file details including URL
    """
    try:
        client = JobTreadPaveClient()
        files = client.get_job_files(PHASE_SPECS_JOB_ID)

        # Find the specific file
        file_data = None
        for f in files:
            if f.get('id') == file_id:
                file_data = f
                break

        if not file_data:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404

        return jsonify({
            'success': True,
            'file': file_data
        })

    except JobTreadAPIError as e:
        logger.error(f"JobTread API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error fetching phase spec file: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch file'
        }), 500
