```markdown
# CodeSentinel Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and workflows of the CodeSentinel Python codebase. You'll learn the project's coding conventions, how to implement coordinated backend or frontend changes, and how to write and organize tests. The repository is structured for modularity and maintainability, with clear conventions for file naming, imports, and exports. Two primary workflows—multi-route backend changes and frontend template/CSS features—are documented with step-by-step instructions and command suggestions.

## Coding Conventions

**File Naming**
- Use `camelCase` for file names.
  - Example: `userProfile.py`, `reviewDetail.html`

**Import Style**
- Use relative imports within the package.
  - Example:
    ```python
    from .models import User
    from .services.auth import authenticate_user
    ```

**Export Style**
- Use named exports (explicitly specifying what is exported).
  - Example:
    ```python
    # In app/services/auth.py
    def authenticate_user(...):
        ...

    __all__ = ['authenticate_user']
    ```

## Workflows

### Multi-Route Backend Change with Tests
**Trigger:** When you need to implement a cross-cutting backend feature or fix (e.g., security, middleware, settings injection) that affects several API endpoints and requires test coverage.  
**Command:** `/multi-route-backend-change`

1. **Edit Multiple Route Handlers:**  
   Update relevant files in `app/routers/` (such as `auth.py`, `billing.py`, `repositories.py`, etc.) to implement your change.
   ```python
   # app/routers/auth.py
   from .middleware import require_secure_headers

   @router.post("/login")
   @require_secure_headers
   def login(...):
       ...
   ```
2. **Update Shared Backend Logic or Middleware:**  
   Modify or add logic in `app/main.py` or `app/services/` as needed.
   ```python
   # app/main.py
   from .middleware import setup_security

   setup_security(app)
   ```
3. **Update or Add Models/Database Logic:**  
   If your change affects data models or database interactions, update files in `app/models/` or `app/database.py`.
   ```python
   # app/models/user.py
   class User(BaseModel):
       ...
   ```
4. **Update or Add Tests:**  
   Ensure new logic is covered by updating or adding tests in `tests/` (e.g., `tests/conftest.py`, `tests/test_auth_router.py`).
   ```python
   # tests/test_auth_router.py
   def test_login_requires_secure_headers(client):
       ...
   ```
5. **Update Dependencies:**  
   If you add new dependencies, update `requirements.txt`.

**Files Involved:**
- `app/routers/auth.py`
- `app/routers/billing.py`
- `app/routers/dashboard.py`
- `app/routers/repositories.py`
- `app/routers/reviews.py`
- `app/routers/rules.py`
- `app/routers/webhooks.py`
- `app/main.py`
- `app/services/`
- `app/models/`
- `app/database.py`
- `tests/conftest.py`
- `tests/test_auth_router.py`
- `requirements.txt`

---

### Frontend Template and CSS Feature
**Trigger:** When you want to introduce a new frontend feature, redesign, or animation that affects several user-facing pages.  
**Command:** `/frontend-feature`

1. **Edit or Add HTML Templates:**  
   Update or create files in `app/templates/` (e.g., `login.html`, `dashboard/index.html`, `partials/job_row.html`).
   ```html
   <!-- app/templates/dashboard/index.html -->
   <div class="new-feature-banner">
       Welcome to the new dashboard!
   </div>
   ```
2. **Update Shared CSS:**  
   Modify `app/static/css/main.css` to implement new styles or animations.
   ```css
   /* app/static/css/main.css */
   .new-feature-banner {
       background: #e0f7fa;
       animation: fadeIn 1s;
   }
   ```
3. **Optionally Update/Add JavaScript:**  
   Add interactivity as needed.
   ```html
   <script>
   document.querySelector('.new-feature-banner').onclick = function() {
       alert('Feature coming soon!');
   }
   </script>
   ```
4. **Test Changes Across Pages:**  
   Manually verify all affected pages for consistency and accessibility.

**Files Involved:**
- `app/templates/auth/login.html`
- `app/templates/auth/magic_link_sent.html`
- `app/templates/base.html`
- `app/templates/dashboard/index.html`
- `app/templates/dashboard/repos.html`
- `app/templates/dashboard/review_detail.html`
- `app/templates/dashboard/reviews.html`
- `app/templates/partials/job_row.html`
- `app/static/css/main.css`

## Testing Patterns

- **Test Framework:** Not explicitly specified, but tests are located in `tests/` and follow the `*.test.*` file pattern.
- **Test File Naming:** Use `*.test.*` (e.g., `test_auth_router.py`).
- **Test Structure:** Tests are organized by feature or route, often with shared fixtures in `tests/conftest.py`.
- **Example:**
  ```python
  # tests/test_auth_router.py
  def test_login_success(client):
      response = client.post("/login", data={...})
      assert response.status_code == 200
  ```

## Commands

| Command                     | Purpose                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| /multi-route-backend-change | Start a coordinated backend change affecting multiple routes with tests. |
| /frontend-feature           | Begin a frontend feature or redesign involving templates and CSS.        |
```
