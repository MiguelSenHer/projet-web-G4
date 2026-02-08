# InSillyClo – Web Project (M2 AMI2B) - Group 4

- Julie FARES
- Cherif SEDDIK
- Miguel SENOVILLA
- Dylane MAUREL

Link to github repository : https://github.com/MiguelSenHer/projet-web-G4
---
Django-based web application for in silico plasmid assembly simulation.

---

## Project structure

```text
projet-web-G4/
├── src/
│   ├── manage.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── accounts/
│   ├── simulator/
│   ├── designer/
│   ├── browse/
│   └── frontend/
│
├── db.sqlite3
└── requirements.txt
```
---

## Requirements

- Python 3.11
- pip
- virtualenv support

---

## Installation

### 1. Create a virtual environment

```
python3.11 -m venv .venv
```

### 2. Activate the virtual environment

```
source .venv/bin/activate
```

### 3. Upgrade pip and install dependencies

```
python -m pip install --upgrade pip  
python -m pip install -r requirements.txt
```

---

## Run the development server

```
python src/manage.py runserver
```

Open your browser at:

http://127.0.0.1:8000/

---

## Applications

- **frontend**: landing page and navigation
- **simulator**: campaign simulation workflow (template upload, validation, inputs)
- **browse**: assembly browsing
- **designer**: template designer
- **accounts**: user authentication and permissions


## Simulate SMTP server - Mailpit (Local Email Testing)
This project uses Mailpit to capture emails locally (password reset, etc.) without sending real emails.

## 1. Installation (Ex. Windows)
- Go to the official Mailpit GitHub: https://github.com/axllent/mailpit
- Click Releases and download mailpit-windows-amd64.zip
- Extract it and get mailpit.exe

## 2. Run Mailpit
- Open CMD in the folder and run:.\mailpit.exe
- Open your browser at:
http://localhost:8025
Mailpit SMTP server runs on 127.0.0.1:1025.
---

## Load data from fixtures to recreate the DB
```
python manage.py loaddata accounts/fixtures/users.json
```
```
python manage.py loaddata accounts/fixtures/accounts.json
```
```
python manage.py loaddata plasmids/fixtures/public_collections.json
```
```
python manage.py loaddata browse/fixtures/browse_data.json
```

## ACCESS TO CREATED USERS ACCOUNTS 
- User accounts
- julie.fares23@gmail.com
- julie.fares25@gmail.com
- marie.dupont26@gmail.com
- paul.dupont@gmail.com
- mimu.mumu@gmail.com
- Lola.Lavoisier@gmail.com
- justine.roger@gmail.com
The password associated to these accounts is 1234567#

---
