from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.portal.auth import create_access_token
from app.db import get_db, crud
from app.models.user import UserCreate, UserStatusCreate # Make sure to import UserStatusCreate
# from app.models.user import UserDataLimitResetStrategy # Import if used in UserCreate defaults

import uuid

router = APIRouter(prefix="/client-portal", tags=["Client Portal Auth"])
templates = Jinja2Templates(directory="app/portal/templates")

# Password-related context and functions are removed as they are no longer needed.

@router.get("/login", response_class=HTMLResponse, name="login_page")
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

@router.get("/register", response_class=HTMLResponse, name="register_page")
async def register_page(request: Request):
    """Render the registration page."""
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )

@router.post("/token", name="login") # For url_for('login') in login.html form
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    account_number = form_data.get("account_number")

    print(f"[DEBUG] Received form data: {form_data}") # DEBUG PRINT
    print(f"[DEBUG] Account number from form: '{account_number}' (type: {type(account_number)})") # DEBUG PRINT

    if not account_number:
        print("[DEBUG] Account Number is missing from form.") # DEBUG PRINT
        raise HTTPException(status_code=400, detail="Account Number is required.")

    # Convert account number to lowercase for case-insensitive comparison
    account_number = account_number.lower()

    print(f"[DEBUG] Calling crud.get_user with account_number: '{account_number}'") # DEBUG PRINT
    user = crud.get_user(db, account_number=account_number)

    if not user:
        print(f"[DEBUG] crud.get_user did not find user for account_number: '{account_number}'") # DEBUG PRINT
        raise HTTPException(status_code=400, detail="Invalid Account Number or account not found.")

    print(f"[DEBUG] User found: {user.account_number if user else 'None'}") # DEBUG PRINT
    access_token = create_access_token(data={"sub": user.account_number})

    redirect_response = RedirectResponse(url="/client-portal/", status_code=303)
    redirect_response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        path='/',
        samesite='lax',
        secure=True, # Assuming HTTPS
        max_age=1800 # 30 minutes
    )
    return redirect_response

@router.post("/register", name="register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    generated_account_number = str(uuid.uuid4())

    # Create the Pydantic model payload, NOW INCLUDING the generated_account_number
    user_payload = UserCreate(
        account_number=generated_account_number, # <--- CRITICAL CHANGE
        proxies={}, # Default as per your existing code
        inbounds=None, # Default as per your existing code
        status=UserStatusCreate.active # Example default status
        # Ensure other required fields in UserCreate (if any beyond account_number)
        # have defaults in the model or are provided here.
        # e.g. data_limit_reset_strategy might need a default or to be set here.
        # Check UserCreate and User model definitions for other non-optional fields without defaults.
    )

    try:
        # crud.create_user expects 'account_number' as a separate argument,
        # and the 'user' Pydantic model.
        new_db_user = crud.create_user(db=db, account_number=generated_account_number, user=user_payload)
    except Exception as e:
        # It's good practice to log the actual error `e` here for debugging
        # import logging
        # logging.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create account due to an internal error.")

    # You're returning JSON, which is fine if your frontend handles it.
    return {"account_number": new_db_user.account_number, "message": "Account created successfully!"}


@router.get("/logout", name="logout")
async def logout_route(response: Response):
    """Handle user logout by deleting the access_token cookie and redirecting."""
    response.delete_cookie(key="access_token", path='/')
    return RedirectResponse(url=router.url_path_for("login_page"), status_code=303)