"""
Files API endpoints for Spines 2.0
"""
from flask import Blueprint, jsonify, request, Response, current_app
from services.file_service import FileService
from utils.auth import require_write_access
from utils.logging import get_logger

logger = get_logger(__name__)
files_api = Blueprint('files_api', __name__)

@files_api.route('/files/upload', methods=['POST'])
@require_write_access
def upload_files():
    """Handle file uploads via drag and drop or file input"""
    try:
        config = current_app.config['SPINES_CONFIG']
        file_service = FileService(config)
        
        contributor = request.form.get('contributor', 'anonymous')
        uploaded_files = request.files.getlist('files')
        
        result = file_service.upload_files(uploaded_files, contributor)
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("File upload failed")
        return jsonify({"error": str(e)}), 500

@files_api.route('/files/process', methods=['POST'])
@require_write_access
def process_files():
    """Process new/modified files via API"""
    try:
        config = current_app.config['SPINES_CONFIG']
        file_service = FileService(config)
        
        data = request.get_json() or {}
        contributor = data.get('contributor', 'anonymous')
        
        result = file_service.process_files(contributor)
        return jsonify(result)
        
    except Exception as e:
        logger.exception("File processing failed")
        return jsonify({"error": str(e)}), 500

@files_api.route('/files/process-stream')
@require_write_access
def process_files_stream():
    """Process files with real-time progress updates via Server-Sent Events"""
    try:
        config = current_app.config['SPINES_CONFIG']
        file_service = FileService(config)
        
        # Get contributor BEFORE creating the generator (while request context is active)
        contributor = request.args.get('contributor', 'anonymous')
        
        # The generator runs outside the original request context, so we
        # need to create a new app context for it to run within.
        app = current_app._get_current_object()
        def stream_with_context():
            with app.app_context():
                yield from file_service.generate_progress_stream(contributor)

        # Set proper headers for SSE
        response = Response(
            stream_with_context(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
        
        return response
        
    except Exception as e:
        logger.exception("File processing stream failed")
        # Return a standard JSON error response, not a 500 HTML page
        return jsonify({"error": str(e)}), 500

@files_api.route('/files/cleanup-temp', methods=['POST'])
@require_write_access
def cleanup_temp():
    """Clean up orphaned temp files"""
    try:
        config = current_app.config['SPINES_CONFIG']
        file_service = FileService(config)
        
        result = file_service.cleanup_temp_files()
        return jsonify(result)
        
    except Exception as e:
        logger.exception("Temp cleanup failed")
        return jsonify({"error": str(e)}), 500

@files_api.route('/files/check-changes')
def check_changes():
    """Check for new or modified files"""
    try:
        config = current_app.config['SPINES_CONFIG']
        file_service = FileService(config)
        
        new_files, modified_files, last_scan_time = file_service.check_for_changes()
        
        return jsonify({
            "new_files": [str(f) for f in new_files],
            "modified_files": [str(f[0]) for f in modified_files],  # f[0] is the file, f[1] is book_id
            "total_changes": len(new_files) + len(modified_files),
            "last_scan_time": last_scan_time
        })
        
    except Exception as e:
        logger.exception("Change check failed")
        return jsonify({"error": str(e)}), 500 