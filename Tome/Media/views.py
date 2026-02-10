from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .models import IPFSUpload


def _unpin_from_ipfs(ipfs_hash):
    """
    Unpin content from local IPFS node.
    
    Args:
        ipfs_hash: The IPFS hash to unpin
        
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not ipfs_hash:
        return True, None
    
    try:
        import ipfshttpclient
        client = ipfshttpclient.connect()
        client.pin.rm(ipfs_hash)
        return True, None
    except Exception as e:
        return False, str(e)


@login_required
def media_list(request):
    """Display all media uploaded by the user"""
    uploads = IPFSUpload.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'uploads': uploads,
    }
    return render(request, 'media/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def media_upload(request):
    """Upload new media to IPFS"""
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        
        if not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
            return render(request, 'media/upload.html')
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if uploaded_file.size > max_size:
            messages.error(request, 'File size exceeds 10MB limit.')
            return render(request, 'media/upload.html')
        
        try:
            # Create IPFSUpload instance
            upload = IPFSUpload.objects.create(
                user=request.user,
                file_stored_on_ipfs=uploaded_file
            )
            
            # Try to upload to IPFS
            ipfs_hash = upload.upload_to_ipfs()
            
            if ipfs_hash:
                messages.success(request, f'File uploaded successfully! IPFS Hash: {ipfs_hash}')
            else:
                messages.warning(request, 'File saved but IPFS upload failed. Make sure IPFS daemon is running.')
            
            return redirect('media_list')
        except Exception as e:
            messages.error(request, f'Error uploading file: {str(e)}')
            return render(request, 'media/upload.html')
    
    return render(request, 'media/upload.html')


@login_required
@require_http_methods(["GET", "POST"])
def media_edit(request, pk):
    """Edit media metadata (mainly to re-upload to IPFS if needed)"""
    upload = get_object_or_404(IPFSUpload, pk=pk, user=request.user)
    
    if request.method == 'POST':
        # Try to re-upload to IPFS
        try:
            ipfs_hash = upload.upload_to_ipfs()
            if ipfs_hash:
                messages.success(request, f'File re-uploaded to IPFS successfully! Hash: {ipfs_hash}')
            else:
                messages.warning(request, 'IPFS upload failed. Make sure IPFS daemon is running.')
            return redirect('media_list')
        except Exception as e:
            messages.error(request, f'Error re-uploading to IPFS: {str(e)}')
    
    context = {
        'upload': upload,
    }
    return render(request, 'media/edit.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def media_delete(request, pk):
    """Delete media and unpin from IPFS"""
    upload = get_object_or_404(IPFSUpload, pk=pk, user=request.user)
    
    if request.method == 'POST':
        # Get details before deletion
        ipfs_hash = upload.ipfs_hash
        file_name = upload.file_stored_on_ipfs.name if upload.file_stored_on_ipfs else 'Unknown'
        
        try:
            # Try to unpin from IPFS if hash exists
            success, error = _unpin_from_ipfs(ipfs_hash)
            
            # Delete the record
            upload.delete()
            
            # Show appropriate message
            if ipfs_hash and not success:
                messages.warning(request, f'File "{file_name}" deleted but unpin failed: {error}')
            else:
                messages.success(request, f'File "{file_name}" deleted successfully.')
            
        except Exception as e:
            messages.error(request, f'Error deleting file: {str(e)}')
        
        return redirect('media_list')
    
    context = {
        'upload': upload,
    }
    return render(request, 'media/delete.html', context)
