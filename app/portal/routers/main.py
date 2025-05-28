from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import httpx
import os
from typing import Optional

from app.db import get_db
from app.portal.models.plan import Plan
from app.portal.auth import get_current_user
from app.models.admin import Admin

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])
templates = Jinja2Templates(directory="app/portal/templates")


@router.get("/", response_class=HTMLResponse)
async def portal_home(request: Request, db: Session = Depends(get_db)):
    """Render the portal home page with available plans."""
    # TODO: Fetch active plans from database
    plans = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "plans": plans}
    )


@router.get("/servers", response_class=HTMLResponse)
async def servers_page(
    request: Request,
    db: Session = Depends(get_db)
):
    """Render the servers page with available nodes/hosts."""
    api_url = os.getenv("API_URL", "https://localhost:8000")
    nodes_data = [] # Use a new variable to hold final data

    try:
        async with httpx.AsyncClient(verify=False) as client:
            print(f"Attempting to fetch nodes from: {api_url}/api/nodes") # Log URL
            response = await client.get(
                f"{api_url}/api/nodes",
                timeout=10.0
            )
            print(f"API Response Status Code: {response.status_code}") # Log Status
            print(f"API Response Text: {response.text}") # Log Raw Text

            response.raise_for_status() # Check for HTTP errors

            nodes = response.json()
            print(f"Received nodes from API: {nodes}")

            # Check if it's a list
            if not isinstance(nodes, list):
                print("Error: API response is not a list!")
                nodes = [] # Set to empty if not a list

            transformed_nodes = []
            for node in nodes:
                # Add host
                node["host"] = node.get("address", "N/A") # Use N/A as default

                # Transform status
                status = node.get("status")
                if status == "error":
                    node["status"] = "Error: " + node.get("message", "Connection failed")
                elif status == "connecting":
                    node["status"] = "Connecting"
                elif not status:
                    node["status"] = "Unknown"

                # Ensure name and port exist for template
                node["name"] = node.get("name", "Unnamed")
                node["port"] = node.get("port", "N/A")

                transformed_nodes.append(node)

            nodes_data = transformed_nodes # Assign transformed data
            print(f"Transformed nodes: {nodes_data}")

    except httpx.RequestError as e:
        print(f"!!! Request error fetching nodes: {str(e)}")
        nodes_data = []
    except httpx.HTTPStatusError as e:
        print(f"!!! HTTP status error: {e.response.status_code} - {e.response.text}")
        nodes_data = []
    except Exception as e:
        import traceback
        print(f"!!! An unexpected error occurred: {str(e)}")
        print(traceback.format_exc()) # Print full traceback
        nodes_data = []

    return templates.TemplateResponse(
        "servers.html",
        {"request": request, "nodes": nodes_data}
    )


def get_plan_by_id(plan_id: str) -> Plan:
    """Get a plan by its ID."""
    # TODO: Fetch from database
    plans = {
        "basic": Plan(
            id="basic",
            name="Basic Plan",
            description="Perfect for individual users",
            price=9.99,
            duration_days=30,
            data_limit=100 * 1024 * 1024 * 1024,  # 100GB
            stripe_price_id="price_basic",
            features=["1 Device", "100GB Data", "30 Days"]
        ),
        "premium": Plan(
            id="premium",
            name="Premium Plan",
            description="For power users and small families",
            price=19.99,
            duration_days=30,
            data_limit=500 * 1024 * 1024 * 1024,  # 500GB
            stripe_price_id="price_premium",
            features=["3 Devices", "500GB Data", "30 Days"]
        ),
        "unlimited": Plan(
            id="unlimited",
            name="Unlimited Plan",
            description="Unlimited data for heavy users",
            price=29.99,
            duration_days=30,
            data_limit=None,  # Unlimited
            stripe_price_id="price_unlimited",
            features=["5 Devices", "Unlimited Data", "30 Days"]
        )
    }
    return plans.get(plan_id)