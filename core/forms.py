from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Product, Brand, Category, Coupon, Address, User, Employee

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'category', 'brand', 'image']

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name']

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']

class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'amount', 'valid_from', 'valid_to', 'active']

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['street_address', 'apartment_address', 'country', 'zip_code', 'address_type', 'default']

class UserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['rut', 'first_name', 'last_name', 'mother_last_name', 'role']