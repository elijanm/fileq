# simple_email_service.py - Plain text email service

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
import uuid
from fastapi import Depends, HTTPException
from pymongo.database import Database
from dataclasses import dataclass
from utils.db import get_database
from metrics.metrics import get_metrics

logger = logging.getLogger(__name__)
import ssl, certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())
@dataclass
class EmailResult:
    status: str  # 'sent' or 'failed'
    email_id: str
    sent_at: str
    error: Optional[str] = None

class EmailService:
    """Simple email service for plain text emails only"""
    
    def __init__(self, db: Database, metrics_collector):
        self.db = db
        self.metrics = metrics_collector
        
        # SMTP Configuration
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.smtp_use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
        self.from_email = os.getenv("FROM_EMAIL", "noreply@example.com")
        self.from_name = os.getenv("FROM_NAME", "Your App")
        self.base_url=os.getenv("BASE_FRONT_URL", "localhost")
        
        # Email tracking
        self.emails_collection = db.emails if db is not None else None
        
        # Initialize collection indexes
        if self.emails_collection is not None :
            try:
                self.emails_collection.create_index([("user_id", 1), ("sent_at", -1)])
                self.emails_collection.create_index([("tenant_id", 1), ("sent_at", -1)])
                self.emails_collection.create_index("email_id", unique=True)
            except Exception as e:
                logger.warning(f"Could not create email indexes: {str(e)}")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        to_name: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        email_type: str = "transactional"
    ) -> EmailResult:
        """Send a plain text email"""
        email_id = str(uuid.uuid4())
        sent_at = datetime.now(timezone.utc).isoformat()
        
        try:
            # Use provided or default sender info
            sender_email = from_email or self.from_email
            sender_name = from_name or self.from_name
            
            # Create message
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender_email}>"
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            msg["Message-ID"] = f"<{email_id}@{sender_email.split('@')[1]}>"
            
            # Send email via SMTP
            await self._send_via_smtp(msg)
            
            # Log successful email
            email_log = {
                "email_id": email_id,
                "to_email": to_email,
                "to_name": to_name,
                "from_email": sender_email,
                "from_name": sender_name,
                "subject": subject,
                "email_type": email_type,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "status": "sent",
                "sent_at": sent_at,
                "error": None
            }
            
            if self.emails_collection is not None:
                self.emails_collection.insert_one(email_log)
            
            logger.info(f"Email sent: {email_id} to {to_email}")
            
            return EmailResult(
                status="sent",
                email_id=email_id,
                sent_at=sent_at
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send email {email_id} to {to_email}: {error_msg}")
            
            # Log failed email
            if self.emails_collection is not None:
                self.emails_collection.insert_one({
                    "email_id": email_id,
                    "to_email": to_email,
                    "to_name": to_name,
                    "from_email": sender_email,
                    "from_name": sender_name,
                    "subject": subject,
                    "email_type": email_type,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "status": "failed",
                    "sent_at": sent_at,
                    "error": error_msg
                })
            
            return EmailResult(
                status="failed",
                email_id=email_id,
                sent_at=sent_at,
                error=error_msg
            )
    
    async def _send_via_smtp(self, msg: MIMEText):
        """Send email via SMTP"""
        context = ssl.create_default_context(cafile=certifi.where())
        
        if self.smtp_use_ssl:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls(context=context)
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
    
    # =====================================
    # PREDEFINED EMAIL TYPES
    # =====================================
    
    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        verification_link: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> EmailResult:
        """Send welcome email"""
        subject = f"Welcome to {self.from_name}!"
        
        message = f"""Hello {user_name},

Welcome to {self.from_name}! We're excited to have you on board.

"""
        
        if verification_link:
            message += f"""To get started, please verify your email address by clicking the link below:
{verification_link}

"""
        
        message += f"""If you have any questions, feel free to reach out to our support team at {os.getenv('SUPPORT_EMAIL', 'support@example.com')}.

Best regards,
The {self.from_name} Team

---
This is an automated message. Please do not reply to this email."""
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            message=message,
            to_name=user_name,
            tenant_id=tenant_id,
            user_id=user_id,
            email_type="welcome"
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_link: str,
        expiry_hours: int = 24,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> EmailResult:
        """Send password reset email"""
        subject = f"Password Reset - {self.from_name}"
        
        message = f"""Hello {user_name},

You requested a password reset for your {self.from_name} account.

Click the link below to reset your password:
{reset_link}

IMPORTANT:
- This link will expire in {expiry_hours} hours
- If you didn't request this reset, please ignore this email
- For security, this link can only be used once

If you continue to have problems, please contact our support team.

Best regards,
The {self.from_name} Team

---
This is an automated security message. Please do not reply to this email."""
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            message=message,
            to_name=user_name,
            tenant_id=tenant_id,
            user_id=user_id,
            email_type="password_reset"
        )
    
    async def send_tenant_invitation_email(
        self,
        to_email: str,
        tenant_name: str,
        inviter_name: str,
        role: str,
        invitation_link: str,
        message_from_inviter: Optional[str] = None,
        expiry_hours: int = 72,
        tenant_id: Optional[str] = None
    ) -> EmailResult:
        """Send tenant invitation email"""
        subject = f"Invitation to {tenant_name} - {self.from_name}"
        
        message = f"""Hello,

{inviter_name} has invited you to join {tenant_name} on {self.from_name}.

Invitation Details:
- Organization: {tenant_name}
- Role: {role.title()}
- Invited by: {inviter_name}

"""
        
        if message_from_inviter:
            message += f"""Personal message from {inviter_name}:
"{message_from_inviter}"

"""
        
        message += f"""Click the link below to accept the invitation:
{invitation_link}

This invitation will expire in {expiry_hours} hours.

Best regards,
The {self.from_name} Team

---
This is an automated invitation. Please do not reply to this email."""
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            message=message,
            tenant_id=tenant_id,
            email_type="invitation"
        )
    async def send_verification_email(self, email: str, token: str, name: Optional[str] = None) -> EmailResult:
        """
        Send a verification email with a verification link.
        """
        user_name = name or "User"

        subject = f"Verify your email address - {self.from_name}"

        # Construct verification link (adjust base_url to match your frontend / gateway)
        verification_url = f"{self.base_url}/verify?token={token}&email={email}"

        message = f"""Hello {user_name},

    Thank you for registering with {self.from_name}. 
    Please verify your email address by clicking the link below:

    {verification_url}

    If you did not create an account, you can safely ignore this email.

    Best regards,  
    The {self.from_name} Team  

    ---  
    This is an automated message. Please do not reply.
    """

        return await self.send_email(
            to_email=email,
            subject=subject,
            message=message,
            to_name=user_name,
            email_type="verification"
        )
    async def send_notification_email(
        self,
        to_email: str,
        user_name: str,
        notification_title: str,
        notification_message: str,
        action_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> EmailResult:
        """Send notification email"""
        subject = f"{notification_title} - {self.from_name}"
        
        message = f"""Hello {user_name},

{notification_message}

"""
        
        if action_url:
            message += f"""For more details, visit:
{action_url}

"""
        
        message += f"""Best regards,
The {self.from_name} Team

---
This is an automated notification. Please do not reply to this email."""
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            message=message,
            to_name=user_name,
            tenant_id=tenant_id,
            user_id=user_id,
            email_type="notification"
        )
    
    # =====================================
    # EMAIL HISTORY & UTILITIES
    # =====================================
    
    async def get_email_history(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        email_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get email history"""
        if not self.emails_collection:
            return []
        
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            if tenant_id:
                query["tenant_id"] = tenant_id
            if email_type:
                query["email_type"] = email_type
            if status:
                query["status"] = status
            
            emails = list(
                self.emails_collection
                .find(query)
                .sort("sent_at", -1)
                .skip(offset)
                .limit(limit)
            )
            
            # Remove _id field
            for email in emails:
                email.pop("_id", None)
            
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get email history: {str(e)}")
            return []
    
    async def bulk_send_emails(
        self,
        recipients: List[Dict[str, str]],  # [{"email": "...", "name": "..."}]
        subject: str,
        message: str,
        tenant_id: Optional[str] = None,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """Send emails to multiple recipients"""
        results = {
            "total": len(recipients),
            "sent": 0,
            "failed": 0,
            "errors": []
        }
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            for recipient in batch:
                try:
                    result = await self.send_email(
                        to_email=recipient["email"],
                        subject=subject,
                        message=message,
                        to_name=recipient.get("name"),
                        tenant_id=tenant_id
                    )
                    
                    if result.status == "sent":
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append({
                            "email": recipient["email"],
                            "error": result.error or "Unknown error"
                        })
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "email": recipient["email"],
                        "error": str(e)
                    })
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Check email service health"""
        try:
            context = ssl.create_default_context()
            
            if self.smtp_use_ssl:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context, timeout=10) as server:
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                    if self.smtp_use_tls:
                        server.starttls(context=context)
                    
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
            
            return {
                "status": "healthy",
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port,
                "from_email": self.from_email
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port
            }

# =====================================
# DEPENDENCY INJECTION
# =====================================

def get_simple_email_service(
    db: Database = Depends(get_database),
    metrics = Depends(get_metrics)
) -> EmailService:
    """Dependency to get simple email service"""
    return EmailService(db, metrics)

# =====================================
# SETUP FUNCTION
# =====================================

def setup_simple_email_service():
    """Setup function to verify email configuration"""
    try:
        smtp_host = os.getenv("SMTP_HOST", "localhost")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
            logger.info(f"Simple email service connection verified: {smtp_host}:{smtp_port}")
            
    except Exception as e:
        logger.error(f"Simple email service connection failed: {str(e)}")

# =====================================
# EXAMPLE USAGE
# =====================================

"""
Example FastAPI routes:

@app.post("/emails/send")
async def send_email(
    to_email: str,
    subject: str,
    message: str,
    email_service: EmailService = Depends(get_simple_email_service)
):
    result = await email_service.send_email(to_email, subject, message)
    return result

@app.post("/emails/welcome")
async def send_welcome(
    to_email: str,
    user_name: str,
    verification_link: Optional[str] = None,
    email_service: EmailService = Depends(get_simple_email_service)
):
    result = await email_service.send_welcome_email(
        to_email, user_name, verification_link
    )
    return result
"""