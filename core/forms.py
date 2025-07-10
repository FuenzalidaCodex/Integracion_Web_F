from django import forms
from django.contrib.auth.forms import UserCreationForm
from django_countries.fields import CountryField
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
    country = CountryField(default='CL').formfield()

    class Meta:
        model = Address
        fields = ['street_address', 'apartment_address', 'city', 'country', 'zip_code', 'address_type', 'default']
        widgets = {
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'aria-label': 'Dirección', 'required': True}),
            'apartment_address': forms.TextInput(attrs={'class': 'form-control', 'aria-label': 'Departamento'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'aria-label': 'Ciudad', 'required': True}),
            'country': forms.Select(attrs={'class': 'form-control', 'aria-label': 'País', 'required': True}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'aria-label': 'Código Postal', 'required': True}),
            'address_type': forms.Select(attrs={'class': 'form-control', 'aria-label': 'Tipo de Dirección', 'required': True}),
            'default': forms.CheckboxInput(attrs={'class': 'form-check-input', 'aria-label': 'Predeterminada'}),
        }

class UserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['rut', 'first_name', 'last_name', 'mother_last_name', 'role']