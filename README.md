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

