import uuid
from typing import Any, Dict, Optional, Union
from sqlalchemy.orm import Session
from app.models.payroll import PayrollAuditLog
from app.models.organization import Organization
from app.models.employee import Employee
from datetime import datetime, date
from decimal import Decimal
import json

class PayrollAuditService:
    @staticmethod
    def log(
        db: Session,
        current_user: Union[Organization, Employee],
        action_type: str,
        entity_type: str,
        entity_id: int,
        employee_id: Optional[int] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
        risk_level: str = "low",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Log a payroll audit event with before/after state comparison.
        """
        org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
        
        # Determine performed_by employee ID
        performed_by_id = None
        if isinstance(current_user, Employee):
            performed_by_id = current_user.id
        else:
            # If Organization user, we need to handle this. 
            # In this system, sensitive actions are usually tied to an admin employee.
            # Fallback to 0 or a system user ID if needed.
            performed_by_id = None
            
        # Calculate changed fields
        changed_fields = {}
        if before_state and after_state:
            for key, value in after_state.items():
                if before_state.get(key) != value:
                    changed_fields[key] = {
                        "old": before_state.get(key),
                        "new": value
                    }

        audit_log = PayrollAuditLog(
            organization_id=org_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            employee_id=employee_id,
            before_state=before_state,
            after_state=after_state,
            changed_fields=changed_fields,
            change_summary=change_summary,
            performed_by=performed_by_id,
            risk_level=risk_level,
            ip_address=ip_address,
            user_agent=user_agent,
            performed_at=datetime.utcnow()
        )
        db.add(audit_log)
        return audit_log

    @staticmethod
    def get_model_dict(model_obj: Any, exclude_fields: Optional[list] = None) -> Dict[str, Any]:
        """
        Convert SQLAlchemy model to dict for audit snapshots.
        Excludes internal IDs and timestamps by default.
        """
        if not model_obj:
            return None
        
        # Default exclusions for cleaner audit logs
        exclude = {'id', 'created_at', 'updated_at', 'organization_id', 'is_exported', 'exported_at'}
        if exclude_fields:
            exclude.update(exclude_fields)
            
        data = {}
        # Get columns from the table mapping
        for column in model_obj.__table__.columns:
            if column.name not in exclude:
                val = getattr(model_obj, column.name)
                # Format specific types for JSON serialization
                if isinstance(val, (datetime, date)):
                    data[column.name] = val.isoformat()
                elif isinstance(val, Decimal):
                    data[column.name] = float(val)
                elif isinstance(val, uuid.UUID):
                    data[column.name] = str(val)
                elif hasattr(val, 'name'): # Enum support
                    data[column.name] = val.name
                else:
                    data[column.name] = val
        return data
