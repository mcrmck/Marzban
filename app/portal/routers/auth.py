from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/client-portal", tags=["Client Portal Auth"])
templates = Jinja2Templates(directory="app/portal/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration page."""
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )


@router.post("/token")
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle user login and return JWT token."""
    form_data = await request.form()
    # TODO: Implement actual user authentication
    # For now, just redirect to home page
    return RedirectResponse(url="/client-portal/", status_code=303)


@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle user registration."""
    form_data = await request.form()
    password = form_data.get("password")
    password_confirm = form_data.get("password_confirm")

    if password != password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # TODO: Implement actual user registration
    # For now, just redirect to login page
    return RedirectResponse(url="/client-portal/auth/login", status_code=303)


@router.get("/logout")
async def logout():
    """Handle user logout."""
    # TODO: Implement actual logout logic
    # For now, just redirect to home page
    return RedirectResponse(url="/client-portal/", status_code=303)