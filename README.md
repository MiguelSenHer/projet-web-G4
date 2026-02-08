# InSillyClo – Web Project (M2 AMI2B) - Group 4

- Julie FARES
- Cherif SEDDIK
- Miguel SENOVILLA

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
│   ├── plasmids/
│   └── frontend/
│
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

```
python -m venv .venv
```

### 2. Activate the virtual environment

Activate the virtual environment depending on your operating system:

On Linux / macOS:

```
source .venv/bin/activate
```

On Windows (PowerShell / CMD):

```
.venv\Scripts\activate
```

### 3. Upgrade pip and install dependencies

```
python -m pip install --upgrade pip  
python -m pip install -r requirements.txt
```

---
### Apply migrations

```
python src/manage.py makemigrations
```

```
python src/manage.py migrate
```

---

## Load data from fixtures to recreate the DB (the order of loading matters)
```
python src/manage.py loaddata src/accounts/fixtures/users.json
```
```
python src/manage.py loaddata src/accounts/fixtures/accounts.json
```
```
python src/manage.py loaddata src/plasmids/fixtures/public_collections.json
```
```
python src/manage.py loaddata src/browse/fixtures/browse_data.json
```

---


## Simulate SMTP server - Mailpit (Local Email Testing)
This project uses Mailpit to capture emails locally (password reset, etc.) without sending real emails.

## 1. Installation
- Go to the official Mailpit GitHub releases: https://github.com/axllent/mailpit/releases
- Download  the archive corresponding to your machine architecture (darwin is macOS), then extract it

## 2. Run Mailpit
- Open a terminal into the extracted folder then run the executable file :

On Windows:

```
.\mailpit.exe
```

On macOS and Linux :

```
./mailpit
```

Note : on macOS, you might need to run this command before : 

```
xattr -d com.apple.quarantine mailpit
```

For any other problems refer to the tool's documentation: https://mailpit.axllent.org/docs/install/


- Open your browser at:
http://localhost:8025
Mailpit SMTP server runs on 127.0.0.1:1025.

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
- **simulator**: campaign simulation workflow (template upload, validation, inputs, outputs)
- **browse**: template assembly browsing
- **designer**: template designer
- **accounts**: user authentication and permissions
- **plasmids**: plasmid visualiser, collections of plasmids and corresponding tables
---

## ACCESS TO CREATED USERS ACCOUNTS

User accounts

- julie.fares23@gmail.com    classic user
- julie.fares25@gmail.com    ADMIN
- marie.dupont26@gmail.com   classic user
- paul.dupont@gmail.com      classic user
- mimu.mumu@gmail.com        classic user
- Lola.Lavoisier@gmail.com   classic user
- justine.roger@gmail.com    ADMIN

The password associated to these accounts is 1234567#

---
