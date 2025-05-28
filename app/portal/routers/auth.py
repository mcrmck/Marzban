from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext  # Import CryptContext


from app.portal.auth import create_access_token
from app.db import get_db
from app.db import crud  # Import crud
from app.models.user import UserCreate  # Import UserCreate


router = APIRouter(prefix="/client-portal", tags=["Client Portal Auth"])
templates = Jinja2Templates(directory="app/portal/templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # Create CryptContext


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


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
@router.post("/token")
async def login(
    request: Request,
    # No need for Response here anymore
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    user = crud.get_user(db, username=username)

    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")


    # Assuming user.hashed_password exists. If not, adjust accordingly.
    # You need to ensure you're fetching the hashed password from the DB via crud.get_user
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": user.username})

    # 1. Create the RedirectResponse
    redirect_response = RedirectResponse(url="/client-portal/", status_code=303)

    # 2. Set the cookie ON the RedirectResponse
    redirect_response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,  # Keeps JS from accessing it
        path='/',       # Ensures it's sent for all paths
        samesite='lax', # Good default for web apps (Lax or Strict)
        secure=True,    # Set this because you run on HTTPS
        max_age=1800    # Optional: e.g., 30 minutes (in seconds)
    )

    # 3. Return the RedirectResponse with the cookie
    return redirect_response

@router.get("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return RedirectResponse(url="/client-portal/login", status_code=303)


@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle user registration."""
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    password_confirm = form_data.get("password_confirm")

    if password != password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = crud.get_user_by_email(db, email=email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(password)
    user_in = UserCreate(
        username=email,
        email=email,
        password=hashed_password,
        proxies={"vmess": {}},  # Add default proxies
        excluded_inbounds = {}
    )
    crud.create_user(db=db, user=user_in)

    return RedirectResponse(url="/client-portal/login", status_code=303)


@router.get("/logout")
async def logout():
    """Handle user logout."""
    # TODO: Implement actual logout logic
    # For now, just redirect to home page
    return RedirectResponse(url="/client-portal/", status_code=303)