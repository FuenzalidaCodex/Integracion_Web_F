from django.db import migrations
from django.contrib.auth.models import User
from core.models import Employee, Category, Brand, Product, Address, Order, OrderItem, Payment

def create_predefined_accounts(apps, schema_editor):
    users_data = [
        {'username': 'admin_user', 'email': 'admin@ferremas.com', 'password': 'Admin123!', 'role': 'admin', 'rut': 'RUT-ADM1'},
        {'username': 'seller_user', 'email': 'seller@ferremas.com', 'password': 'Seller123!', 'role': 'seller', 'rut': 'RUT-SEL1'},
        {'username': 'warehouse_user', 'email': 'warehouse@ferremas.com', 'password': 'Warehouse123!', 'role': 'warehouse', 'rut': 'RUT-WHS1'},
        {'username': 'accountant_user', 'email': 'accountant@ferremas.com', 'password': 'Accountant123!', 'role': 'accountant', 'rut': 'RUT-ACC1'},
    ]

    for user_data in users_data:
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password']
        )
        Employee.objects.create(
            user=user,
            rut=user_data['rut'],
            first_name=user_data['username'].split('_')[0].capitalize(),
            last_name='Lastname',
            role=user_data['role']
        )
        # UserProfile creation handled by signal in models.py

    category = Category.objects.create(name='Herramientas', description='Herramientas de construcción')
    brand = Brand.objects.create(name='FERREMAS')
    product = Product.objects.create(
        name='Taladro Eléctrico',
        description='Taladro de alta potencia',
        price=49990.00,
        stock=50,
        category=category,
        brand=brand
    )
    address = Address.objects.create(
        user=User.objects.get(username='seller_user'),
        street_address='Av. Principal 123',
        zip_code='8320000',
        country='CL',
        address_type='S',
        default=True
    )
    order = Order.objects.create(
        user=User.objects.get(username='seller_user'),
        shipping_address=address,
        status='pending'
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=2,
        price=product.price
    )
    Payment.objects.create(
        order=order,
        amount=order.get_total(),
        method='credit',
        stripe_payment_intent_id='pi_test_123',
        confirmed=False
    )

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_predefined_accounts),
    ]