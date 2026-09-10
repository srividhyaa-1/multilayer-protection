from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from .models import UserProfile, UploadedFile, KeyRequest
from django.contrib.auth.decorators import login_required

from Crypto.Cipher import DES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from django.core.files.base import ContentFile
from django.http import FileResponse
import base64

def home(request):
    return render(request, 'home.html')

# Vendor/Client Registration
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            return render(request, 'register.html', {
                'error': 'Passwords do not match'
            })

        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {
                'error': 'Username already exists'
            })

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        UserProfile.objects.create(
            user=user,
            role='vendor'
        )

        return redirect('login')

    return render(request, 'register.html')


# Vendor/Client Login
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)

            if user.is_superuser:
                return redirect('admin_dashboard')
            else:
                return redirect('dashboard')

        return render(request, 'login.html', {
            'error': 'Invalid username or password'
        })

    return render(request, 'login.html')

# Vendor/Client Dashboard
def dashboard(request):
    return render(request, 'dashboard.html')

def upload_file(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')

        if uploaded_file:
            # Read the uploaded file
            file_data = uploaded_file.read()

            # Generate DES key and IV
            key = get_random_bytes(8)
            iv = get_random_bytes(8)

            # Create DES cipher
            cipher = DES.new(key, DES.MODE_CBC, iv)

            # Encrypt the file
            encrypted_data = cipher.encrypt(
                pad(file_data, DES.block_size)
            )

            # Convert key and IV to text
            encoded_key = base64.b64encode(key).decode('utf-8')
            encoded_iv = base64.b64encode(iv).decode('utf-8')

            # Create database record
            encrypted_file = UploadedFile(
                user=request.user,
                encryption_key=encoded_key,
                iv=encoded_iv
            )

            # Save encrypted file
            encrypted_filename = uploaded_file.name + '.enc'

            encrypted_file.file.save(
                encrypted_filename,
                ContentFile(encrypted_data)
            )

            return render(request, 'upload_file.html', {
                'message': 'File encrypted and uploaded successfully!'
            })

    return render(request, 'upload_file.html')

def view_files(request):
    files = UploadedFile.objects.filter(user=request.user)

    return render(request, 'view_files.html', {
        'files': files
    })

def request_key(request):
    files = UploadedFile.objects.filter(user=request.user)

    if request.method == 'POST':
        file_id = request.POST.get('file_id')

        uploaded_file = UploadedFile.objects.get(
            id=file_id,
            user=request.user
        )

        KeyRequest.objects.create(
            user=request.user,
            uploaded_file=uploaded_file
        )

        return render(request, 'request_key.html', {
            'files': files,
            'message': 'Encryption key request sent to Admin successfully!'
        })

    return render(request, 'request_key.html', {
        'files': files
    })

def decrypt_file(request, file_id):
    uploaded_file = UploadedFile.objects.get(
        id=file_id,
        user=request.user
    )

    # Check whether Admin approved the key request
    key_request = KeyRequest.objects.filter(
        uploaded_file=uploaded_file,
        user=request.user,
        status='approved'
    ).first()

    if not key_request:
        return render(request, 'view_files.html', {
            'files': UploadedFile.objects.filter(user=request.user),
            'error': 'Admin has not approved your key request.'
        })

    # Get the DES key and IV
    key = base64.b64decode(uploaded_file.encryption_key)
    iv = base64.b64decode(uploaded_file.iv)

    # Read encrypted file
    with uploaded_file.file.open('rb') as f:
        encrypted_data = f.read()

    # Decrypt the file
    cipher = DES.new(key, DES.MODE_CBC, iv)

    decrypted_data = unpad(
        cipher.decrypt(encrypted_data),
        DES.block_size
    )

    # Download the original file
    response = FileResponse(
        ContentFile(decrypted_data),
        as_attachment=True,
        filename=uploaded_file.file.name.replace('.enc', '')
    )

    return response



@login_required
def admin_dashboard(request):

    # Check whether the logged-in user is an admin
    if not request.user.is_superuser:
        return render(request, 'dashboard.html', {
            'error': 'You are not authorized to access the Admin Dashboard.'
        })

    key_requests = KeyRequest.objects.all().order_by('-requested_at')

    total_requests = key_requests.count()
    pending_requests = key_requests.filter(status='pending').count()
    approved_requests = key_requests.filter(status='approved').count()
    rejected_requests = key_requests.filter(status='rejected').count()

    return render(request, 'admin_dashboard.html', {
        'key_requests': key_requests,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
    })
@login_required
def approve_request(request, request_id):

    if not request.user.is_superuser:
        return redirect('login')

    key_request = KeyRequest.objects.get(id=request_id)

    key_request.status = 'approved'
    key_request.save()

    return redirect('admin_dashboard')


@login_required
def reject_request(request, request_id):

    if not request.user.is_superuser:
        return redirect('login')

    key_request = KeyRequest.objects.get(id=request_id)

    key_request.status = 'rejected'
    key_request.save()

    return redirect('admin_dashboard')

def admin_login(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_superuser:

            login(request, user)

            return redirect('admin_dashboard')

        return render(request, 'admin_login.html', {
            'error': 'Invalid admin username or password.'
        })

    return render(request, 'admin_login.html')