#!/usr/bin/env python3
"""
Setup script to create organizations and users for HR Chatbot
"""

import sys
from models import create_database, Organization, User
from config import Config
import uuid

def create_organization(db_session, name, domain):
    """Create a new organization"""
    try:
        # Check if organization exists
        existing_org = db_session.query(Organization).filter(
            Organization.domain == domain
        ).first()
        
        if existing_org:
            print(f"Organization {name} already exists with API key: {existing_org.api_key}")
            return existing_org
        
        # Create new organization
        org = Organization(
            name=name,
            domain=domain,
            api_key=str(uuid.uuid4())
        )
        
        db_session.add(org)
        db_session.commit()
        
        print(f"Created organization: {name}")
        print(f"Domain: {domain}")
        print(f"API Key: {org.api_key}")
        print(f"Organization ID: {org.id}")
        
        return org
        
    except Exception as e:
        print(f"Error creating organization: {e}")
        db_session.rollback()
        return None

def main():
    """Main setup function"""
    if len(sys.argv) < 3:
        print("Usage: python setup_organization.py <organization_name> <domain>")
        print("Example: python setup_organization.py 'Acme Corp' 'acme.com'")
        sys.exit(1)
    
    org_name = sys.argv[1]
    domain = sys.argv[2]
    
    # Initialize database
    engine, SessionLocal = create_database(Config.DATABASE_URL)
    db_session = SessionLocal()
    
    try:
        # Create organization
        org = create_organization(db_session, org_name, domain)
        
        if org:
            print("\n" + "="*50)
            print("SETUP COMPLETE!")
            print("="*50)
            print(f"Organization: {org.name}")
            print(f"API Key: {org.api_key}")
            print(f"Domain: {org.domain}")
            print("\nSave this API key - you'll need it to authenticate API requests!")
            print("="*50)
        
    finally:
        db_session.close()

if __name__ == "__main__":
    main()