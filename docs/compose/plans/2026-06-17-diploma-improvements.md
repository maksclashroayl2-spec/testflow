# Testflow Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical bugs and add missing features to the TestFlow project.

**Architecture:** Incremental improvements to existing Django project — fix bugs first, then add missing infrastructure (tests, Docker, API, etc.).

**Tech Stack:** Django, PostgreSQL/SQLite, DRF, Docker, pytest

---

### Task 1: Fix teacher_students URL bug

**Files:**
- Modify: `tests_app/urls.py`

- [ ] Add missing URL pattern for `teacher_students` view
- [ ] Verify the URL works

### Task 2: Add LOGGING config

**Files:**
- Modify: `testflow_project/settings.py`

- [ ] Add Django LOGGING configuration

### Task 3: Add custom error pages

**Files:**
- Create: `tests_app/templates/404.html`
- Create: `tests_app/templates/500.html`
- Modify: `testflow_project/settings.py` (TEMPLATES config)

- [ ] Create 404.html template
- [ ] Create 500.html template
- [ ] Configure Django to use custom error pages

### Task 4: Add database indexes

**Files:**
- Create: `tests_app/migrations/0014_add_indexes.py`

- [ ] Add indexes on Result.student, Result.test, Question.test

### Task 5: Add unit tests

**Files:**
- Modify: `tests_app/tests.py`

- [ ] Write tests for models (Profile, Test, Question, Answer, Result)
- [ ] Write tests for views (home, login, register, test taking flow)
- [ ] Write tests for forms (TestForm validation)

### Task 6: Add Docker setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] Create Dockerfile
- [ ] Create docker-compose.yml with PostgreSQL
- [ ] Create .dockerignore

### Task 7: Add REST API with DRF

**Files:**
- Modify: `requirements.txt`
- Modify: `testflow_project/settings.py`
- Create: `tests_app/serializers.py`
- Create: `tests_app/api_views.py`
- Modify: `testflow_project/urls.py`

- [ ] Add DRF to requirements and settings
- [ ] Create serializers for Test, Question, Result
- [ ] Create API views
- [ ] Wire up API URLs

### Task 8: Add rate limiting

**Files:**
- Modify: `requirements.txt`
- Modify: `testflow_project/settings.py`
- Modify: `tests_app/views.py` (login_view)

- [ ] Add django-ratelimit
- [ ] Apply rate limiting to login view

### Task 9: Add caching

**Files:**
- Modify: `testflow_project/settings.py`
- Modify: `tests_app/views.py`

- [ ] Configure Django cache backend
- [ ] Add cache to home page stats
- [ ] Add cache to tests list

### Task 10: Add README.md

**Files:**
- Create: `README.md`

- [ ] Write project documentation
