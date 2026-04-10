from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.db.base import Base

class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    note = Column(String, nullable=True)

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    note = Column(String, nullable=True)

class AssetType(Base):
    __tablename__ = 'asset_types'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category_group = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    note = Column(String, nullable=True)

class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    site_group = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    note = Column(String, nullable=True)
