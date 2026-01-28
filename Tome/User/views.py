from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.db import IntegrityError

# Create your views here.
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate required fields
        if not username or not email or not password or not confirm_password:
            messages.error(request, 'All fields are required.')
            return render(request, 'register/index.html')
        
        # Validate passwords match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register/index.html')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register/index.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'register/index.html')
        
        # Create user with race condition handling
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            
            # Log the user in
            auth_login(request, user)
            
            messages.success(request, 'Registration successful!')
            return redirect('home')
        except IntegrityError:
            messages.error(request, 'Username or email already exists.')
            return render(request, 'register/index.html')
    
    return render(request, 'register/index.html')
def login(request):
    return render(request, 'login/index.html')
def home(request):
    return render(request, 'home/index.html')