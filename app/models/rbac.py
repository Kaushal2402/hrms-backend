from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, ForeignKey, Index, text, ARRAY, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.db.base_class import Base
from app.models.organization import GUID

class RoleType(Base):
    __tablename__ = "role_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), index=True)

    # Role Details
    role_code = Column(String(100), nullable=False)
    role_name = Column(String(150), nullable=False)
    role_description = Column(Text)

    # Role Type
    role_type_id = Column(Integer, ForeignKey('role_types.id'), index=True)
    role_type = relationship("RoleType")

    # Hierarchy
    parent_role_id = Column(Integer, ForeignKey('roles.id'))
    role_level = Column(Integer, default=0)

    # Scope
    scope = Column(String(50), default='organization')

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_system_role = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)

    # Permissions Inheritance
    inherit_permissions = Column(Boolean, default=True)

    # Display
    display_order = Column(Integer, default=0)
    color_code = Column(String(20))
    icon = Column(String(50))

    # Soft Delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'))
    updated_by = Column(Integer, ForeignKey('employees.id'))

    # Relationships
    organization = relationship("Organization")
    parent_role = relationship("Role", remote_side=[id])
    sub_roles = relationship("Role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            'uniq_role_org_code_active',
            'organization_id',
            'role_code',
            text("(CASE WHEN is_deleted THEN uuid ELSE '0' END)"),
            unique=True
        ),
    )


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)

    # Permission Identity
    permission_code = Column(String(150), nullable=False, unique=True, index=True)
    permission_name = Column(String(200), nullable=False)
    permission_description = Column(Text)

    # Resource & Action
    resource = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False)

    # Module Classification
    module = Column(String(100), nullable=False, index=True)
    sub_module = Column(String(100))

    # Permission Type
    permission_type = Column(String(50), default='standard')

    # API Endpoint Pattern
    api_endpoint_pattern = Column(String(500))
    http_methods = Column(JSON)

    # Dependency
    depends_on_permission_ids = Column(JSON)

    # Risk Level
    risk_level = Column(String(20), default='low')

    # System Permission
    is_system_permission = Column(Boolean, default=False)

    # Status
    is_active = Column(Boolean, default=True)

    # Display
    display_order = Column(Integer, default=0)
    category = Column(String(100))

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True)

    # Grant Type
    grant_type = Column(String(20), default='allow')

    # Conditional Access
    conditions = Column(JSON)

    # Data Scope
    data_scope = Column(String(50), default='all')

    # Field-Level Access
    field_restrictions = Column(JSON)

    # Time-based Access
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'))

    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uniq_role_perm'),
    )



class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)

    # Assignment Context
    assigned_by = Column(Integer, ForeignKey('employees.id'))
    assignment_reason = Column(Text)

    # Scope Restrictions
    department_ids = Column(JSON)
    location_ids = Column(JSON)
    employee_ids = Column(JSON)

    # Time-based Assignment
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime)

    # Primary Role
    is_primary = Column(Boolean, default=False)

    # Status
    is_active = Column(Boolean, default=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'))

    # Relationships
    role = relationship("Role", back_populates="users")
    # user relationship would go here if User model was imported
    # user = relationship("User", foreign_keys=[user_id])
