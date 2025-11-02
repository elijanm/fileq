from fastapi import APIRouter, HTTPException, Request, Body
from core.database import get_database
from plugins.ticketing.models import Ticket,Comment,TicketCreate
from datetime import datetime,timezone
from routes.auth import get_current_user,checker,Depends,SessionInfo

router = APIRouter()




# --- Create ticket ---
@router.post("/", response_model=Ticket)
async def create_ticket(request:Request,ticket: TicketCreate,user:SessionInfo=Depends(get_current_user)):
    tickets = request.app.state.adb["tickets"]
    
    ticket_doc = Ticket(
        **ticket.model_dump(),
        created_by=user.user_id,
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )
    data=ticket_doc.model_dump(by_alias=True)
    await tickets.insert_one(data)
    return data


# --- List / Filter tickets ---
@router.get("/", response_model=list[Ticket])
async def list_tickets(request:Request,status: str | None = None, assigned_to: str | None = None):
    tickets = request.app.state.adb["tickets"]
    query = {}
    if status:
        query["status"] = status
    if assigned_to:
        query["assigned_to"] = assigned_to
    result = await tickets.find(query).sort("created_at", -1).to_list(100)
    
    return result


# --- Get single ticket ---
@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(request:Request,ticket_id: str):
    tickets = request.app.state.adb["tickets"]
    ticket = await tickets.find_one({"_id": ticket_id})
    
    if not ticket:
        raise HTTPException(404, detail="Ticket not found")
    return ticket


# --- Update / assign ticket ---
@router.put("/{ticket_id}", response_model=Ticket)
async def update_ticket(request:Request,ticket_id: str, data: dict = Body(...)):
    tickets = request.app.state.adb["tickets"]
    data["updated_at"] = datetime.now(timezone.utc)
    await tickets.update_one({"_id": ticket_id}, {"$set": data})
    ticket = await tickets.find_one({"_id": ticket_id})
    
    if not ticket:
        raise HTTPException(404, detail="Ticket not found")
    return ticket





# --- Close ticket ---
@router.post("/{ticket_id}/close")
async def close_ticket(request:Request,ticket_id: str):
    tickets = request.app.state.adb["tickets"]
    result = await tickets.update_one(
        {"_id": ticket_id},
        {"$set": {"status": "closed", "updated_at": datetime.now(timezone.utc)}},
    )
    
    if result.modified_count == 0:
        raise HTTPException(404, detail="Ticket not found")
    return {"status": "closed"}

# --- List comments for a ticket ---
@router.get("/{ticket_id}/comments", response_model=list[Comment])
async def list_comments(request:Request,ticket_id: str):
    tickets = request.app.state.adb["tickets"]
    ticket = await tickets.find_one({"_id": ticket_id}, {"comments": 1, "_id": 0})
    
    if not ticket:
        raise HTTPException(404, detail="Ticket not found")
    return ticket.get("comments", [])


# --- Add a new comment ---
@router.post("/{ticket_id}/comments", response_model=Comment)
async def add_comment(request:Request,ticket_id: str, comment: Comment = Body(...)):
    tickets = request.app.state.adb["tickets"]

    comment.created_at = datetime.utcnow()
    comment_dict = comment.model_dump(by_alias=True)

    result = await tickets.update_one(
        {"_id": ticket_id},
        {"$push": {"comments": comment_dict}, "$set": {"updated_at": datetime.utcnow(),"status":"open"}},
    )

    if result.matched_count == 0:
        
        raise HTTPException(404, detail="Ticket not found")

    
    return comment


# --- Delete a comment ---
@router.delete("/{ticket_id}/comments/{comment_id}")
async def delete_comment(request:Request,ticket_id: str, comment_id: str):
    tickets = request.app.state.adb["tickets"]

    result = await tickets.update_one(
        {"_id": ticket_id},
        {"$pull": {"comments": {"_id": comment_id}}, "$set": {"updated_at": datetime.utcnow()}},
    )

    
    if result.modified_count == 0:
        raise HTTPException(404, detail="Ticket or comment not found")

    return {"status": "deleted", "comment_id": comment_id}
