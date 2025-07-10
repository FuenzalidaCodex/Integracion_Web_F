# Integracion_Web_F
2025_1_PN_ASY5131_24292747_PCT - INTEGRACION DE PLATAFORMAS - WEB FERREMAS

1-Crear o usar base de datos ferremas_db, usar el siguiente puerto y contraseña en Mysql:
'NAME': 'ferremas_db',
'USER': 'root',
'PASSWORD': 'root',
'HOST': 'localhost',
'PORT': '3306',

2-Crear y activar entorno virtual:
python -m venv env
env\Scripts\activate    

3-Instalar Dependencias:
pip install -r requirements.txt

4-Hacer migraciones:
python manage.py makemigrations
python manage.py migrate   

5-Iniciar Web:
python manage.py runserver 


*Usuarios y contraseña para datos importantes de testeo:
admin_user          Admin123!
seller_user         Seller123!
warehouse_user      Warehouse123!
accountant_user     Accountant123!


*Si se usa la base de datos entregada ferremas_db es:
admin_user          test123456
seller_user         test123456
warehouse_user      test123456
accountant_user     test123456