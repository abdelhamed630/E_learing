# 🎓 E-Learning Platform — Backend API

A full-featured, production-ready e-learning platform REST API built with Django & Django REST Framework. Supports students, instructors, course management, payments, exams, and real-time notifications.

---

## 🚀 Features

### 👤 Accounts & Auth
- Custom user model with 3 roles: **Student / Instructor / Admin**
- JWT authentication with token rotation
- Email verification with time-limited tokens
- Password reset via async email (Celery + Redis)
- Login history tracking (IP, device, location)

### 📚 Courses
- Full course management: categories, sections, videos, attachments
- Course reviews & nested comments with likes
- Advanced filtering, full-text search, pagination
- Free & paid video support with downloadable attachments
- Discount pricing system

### 👨‍🎓 Students & Instructors
- Separate student and instructor profiles
- Instructor dashboard with course analytics
- Student enrollment tracking and progress

### 📝 Exams
- Exam creation and management per course
- Granular permissions for exam access
- Automated result processing via Celery

### 💳 Payments
- Payment processing with order management
- Async payment confirmation emails
- Payment history and status tracking

### 🔔 Notifications
- Real-time notification system
- Async delivery via Celery + Redis
- Custom notification types per event

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Framework | Django 4.2, Django REST Framework 3.15 |
| Auth | JWT (SimpleJWT), RBAC |
| Database | PostgreSQL |
| Cache & Queue | Redis, Celery, django-celery-beat |
| Deployment | Docker, Docker Compose, Nginx, Gunicorn |
| Filtering | django-filter |
| CORS | django-cors-headers |

---

## 📁 Project Structure

```
E_Learning/
├── accounts/        # Auth, users, email verification
├── students/        # Student profiles & management
├── instructors/     # Instructor profiles & dashboard
├── courses/         # Courses, sections, videos, reviews
├── enrollments/     # Student enrollments & progress
├── exams/           # Exams & results
├── payments/        # Payment processing
├── notifications/   # Notification system
├── core/            # Shared utilities, mixins, validators
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## ⚙️ Quick Start

### Using Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/abdelhamed630/e-learning-backend
cd e-learning-backend

# 2. Copy environment variables
cp .env.example .env

# 3. Build and run
docker-compose up --build
```

API will be available at: `http://localhost:8000`

### Manual Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment variables
cp .env.example .env

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Start Redis (required for Celery)
redis-server

# 7. Start Celery worker
celery -A E_Learning worker -l info

# 8. Run development server
python manage.py runserver
```

---

## 🔑 Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=elearning_db
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Redis & Celery
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=your_app_password
```

---

## 📡 API Endpoints

| Module | Base URL | Description |
|--------|----------|-------------|
| Accounts | `/api/accounts/` | Register, login, logout, password reset |
| Students | `/api/students/` | Student profiles & management |
| Instructors | `/api/instructors/` | Instructor profiles & dashboard |
| Courses | `/api/courses/` | Course CRUD, videos, reviews |
| Enrollments | `/api/enrollments/` | Enroll, track progress |
| Exams | `/api/exams/` | Exam management & results |
| Payments | `/api/payments/` | Payment processing |
| Notifications | `/api/notifications/` | User notifications |

---

## 🧪 Running Tests

```bash
python manage.py test
# or
pytest
```

---

## 🐳 Docker Services

```yaml
services:
  web      # Django + Gunicorn
  db       # PostgreSQL
  redis    # Redis for Celery & caching
  celery   # Async task worker
  nginx    # Reverse proxy
```

---

## 👨‍💻 Author

**Abdelhamed Mostafa** — Backend Developer

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/abdelhmed-mostafe-111118307)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)](https://github.com/abdelhamed630)
[![Email](https://img.shields.io/badge/Email-D14836?style=flat&logo=gmail&logoColor=white)](mailto:abdelhamed.mostafa@gmail.com)
