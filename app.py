
import eventlet
from importlib.metadata.diagnose import inspect
from logging.handlers import RotatingFileHandler
from operator import and_
from sqlalchemy import MetaData, Table
from sqlalchemy import MetaData, Table
import csv
import io
from threading import Thread
from flask_migrate import Migrate
import time
from flask import Flask, abort, Blueprint, make_response, render_template, request, redirect, send_from_directory, url_for, flash, session, jsonify, send_file
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import openai
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date, timezone

# EAT (East African Time) is UTC+3
EAT = timezone(timedelta(hours=3))

def get_eat_now():
    """Get current time in EAT (East African Time - UTC+3)"""
    return datetime.now(EAT)

from sqlalchemy import create_engine, func, literal
from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from config import Config 
import random
import string
from flask import jsonify, request, current_app
from sqlalchemy import or_
from flask_migrate import Migrate
import json
from werkzeug.utils import secure_filename
import os 
from flask import send_file
import tempfile
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
import boto3 
import uuid
from datetime import datetime, timezone
import zipfile
import hashlib
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI, APITimeoutError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
from itsdangerous import URLSafeTimedSerializer
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from sqlalchemy import event, text as sa_text
import uuid as _uuid
import re
from markupsafe import Markup, escape

# Initialize Flask app
app = Flask(__name__)

def nl2br(value):
    """Convert newlines to <br> tags"""
    if not value:
        return ""
    # Normalize line endings and convert to <br> tags
    value = re.sub(r'\r\n|\r|\n', '\n', str(value))
    return Markup(value.replace('\n', '<br>\n'))

app.jinja_env.filters['nl2br'] = nl2br



# Production configuration for Render
if os.environ.get('RENDER'):
    # Production settings
    app.config.update(
        DEBUG=False,
        TESTING=False,
        PREFERRED_URL_SCHEME='https'
    )
    
    # Setup logging for production
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler('logs/clinic.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Clinic Management System starting in production mode')
else:
    # Development settings
    app.config.update(
        DEBUG=True,
        TESTING=True,
        PREFERRED_URL_SCHEME='http'
    )
    app.logger.setLevel(logging.DEBUG)
    app.logger.info('Clinic Management System starting in development mode')

app.config.from_object('config.Config')
Config.init_fernet(app)
db = SQLAlchemy(app, session_options={"autoflush": False, "autocommit": False})
migrate = Migrate(app, db)
# Socket.IO removed - using standard Flask dev server

auth_bp = Blueprint('auth', __name__)
csrf = CSRFProtect()
# Configure rate limit storage backend via env or config; default to in-memory for development
app.config['RATELIMIT_STORAGE_URI'] = os.getenv(
    'RATELIMIT_STORAGE_URI',
    app.config.get('RATELIMIT_STORAGE_URI', 'memory://')
)
limiter = Limiter(key_func=get_remote_address, storage_uri=app.config['RATELIMIT_STORAGE_URI'])
# Ensure CSRF and Limiter are initialized on the app
csrf.init_app(app)
limiter.init_app(app)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
PROFILE_PICTURE_FOLDER = os.path.join(UPLOAD_FOLDER, 'profile_pictures')
os.makedirs(PROFILE_PICTURE_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'U3VwZXJTZWNyZXRBZG1pblRva2VuMTIzIQ')  # Provide default only for development
def get_database_uri():
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Handle both PostgreSQL URL formats
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url
    else:
        # Fallback to SQLite for local development
        return 'sqlite:///clinic.db'
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', UPLOAD_FOLDER)
app.config['BACKUP_FOLDER'] = os.getenv('BACKUP_FOLDER', 'backups')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max upload size
app.config.from_object(Config)
app.config['FERNET_KEY'] = os.getenv('FERNET_KEY')
app.config['DEEPSEEK_API_KEY'] = os.getenv('DEEPSEEK_API_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your.email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-password-or-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'your.email@gmail.com')




mail = Mail(app)
ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures')):
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures'))


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

# Database Models
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)  # Increased from 50
    email = db.Column(db.String(255), unique=True, nullable=False)    # Increased from 100
    password = db.Column(db.String(255), nullable=False)              # Increased from 200
    role = db.Column(db.String(50), nullable=False, default='user')   # Increased from 20
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    profile_picture = db.Column(db.Text)  # Changed from String(255) to Text for long URLs
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def get_id(self):
        return str(self.id)
        # Relationship to Sales (as pharmacist)
    def update_last_login(self):
        self.last_login = get_eat_now()
        db.session.commit()
    # Relationships 
    generated_summaries = db.relationship('PatientSummary', back_populates='generator', lazy=True)

class BackupRecord(db.Model):
    __tablename__ = 'backup_records'

    id = db.Column(db.Integer, primary_key=True)
    backup_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    backup_type = db.Column(db.String(20), nullable=False)  # 'manual', 'scheduled', 'disaster_recovery'
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    size_bytes = db.Column(db.Integer)
    storage_location = db.Column(db.String(255))  # S3 path or local path
    checksum = db.Column(db.String(64))  # SHA-256 checksum
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    notes = db.Column(db.Text)
    
    user = db.relationship('User', backref='backups')
    
    def __repr__(self):
        return f'<BackupRecord {self.backup_id}>'

class DisasterRecoveryPlan(db.Model):
    __tablename__ = 'disaster_recovery_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    recovery_point_objective = db.Column(db.Integer)  # in minutes
    recovery_time_objective = db.Column(db.Integer)  # in minutes
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_tested = db.Column(db.DateTime)
    test_results = db.Column(db.Text)
    
    def __repr__(self):
        return f'<DisasterRecoveryPlan {self.name}>'

class Ward(db.Model):
    __tablename__ = 'wards'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    beds = db.relationship('Bed', backref='ward', lazy=True)

class Bed(db.Model):
    __tablename__ = 'beds'
    
    id = db.Column(db.Integer, primary_key=True)
    bed_number = db.Column(db.String(50), nullable=False, unique=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    status = db.Column(db.String(20), default='available')  # available, occupied, maintenance
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    patient = db.relationship('Patient', backref='bed_assignment')

def get_total_beds():
    return Bed.query.count()

def get_available_beds():
    return Bed.query.options(db.joinedload(Bed.patient)).filter_by(status='available').count()

def get_occupied_beds():
    return Bed.query.options(db.joinedload(Bed.patient)).filter_by(status='occupied').count()

class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_number = db.Column(db.String(100), unique=True, nullable=False)  # Increased from 50
    name = db.Column(db.String(255), nullable=False)                      # Increased from 100
    specification = db.Column(db.Text)                                    # Changed from String(200) to Text
    buying_price = db.Column(db.Numeric(10, 2), nullable=False)           # Use Numeric for money
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)          # Use Numeric for money
    stocked_quantity = db.Column(db.Integer, nullable=False)
    sold_quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @hybrid_property
    def remaining_quantity(self):
        return self.stocked_quantity - (self.sold_quantity or 0)
    
    @remaining_quantity.expression
    def remaining_quantity(cls):
        return cls.stocked_quantity - (cls.sold_quantity or 0)
    
    def update_stock(self, quantity):
        """Safe method to update stock quantities"""
        if self.remaining_quantity >= quantity:
            self.sold_quantity += quantity
            db.session.add(self)
            return True
        return False
    
    @hybrid_property
    def stock_status(self):
        remaining = self.remaining_quantity
        if remaining <= 0:
            return 'out-of-stock'
        elif remaining < 10:
            return 'low-stock'
        elif self.expiry_date and (self.expiry_date - date.today()).days < 30:
            return 'expiring-soon'
        return 'in-stock'
    
    @stock_status.expression
    def stock_status(cls):
        return case([
            (cls.remaining_quantity == 0, 'out-of-stock'),
            (cls.remaining_quantity < 10, 'low-stock'),
            (cls.expiry_date <= date.today() + timedelta(days=30), 'expiring-soon')
        ], else_='in-stock')
    
    def update_stock(self, quantity):
        """Safe method to update stock quantities"""
        if self.remaining_quantity >= quantity:
            self.sold_quantity += quantity  # Update the underlying column
            return True
        return False  


class ControlledDrug(db.Model):
    __tablename__ = 'controlled_drugs'

    id = db.Column(db.Integer, primary_key=True)
    controlled_drug_number = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    specification = db.Column(db.Text)
    buying_price = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)
    stocked_quantity = db.Column(db.Integer, nullable=False)
    sold_quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @hybrid_property
    def remaining_quantity(self):
        return self.stocked_quantity - (self.sold_quantity or 0)

    @remaining_quantity.expression
    def remaining_quantity(cls):
        return cls.stocked_quantity - (cls.sold_quantity or 0)

    @hybrid_property
    def stock_status(self):
        remaining = self.remaining_quantity
        if remaining <= 0:
            return 'out-of-stock'
        if remaining < 10:
            return 'low-stock'
        if self.expiry_date and (self.expiry_date - date.today()).days < 30:
            return 'expiring-soon'
        return 'in-stock'


class ControlledPrescription(db.Model):
    __tablename__ = 'controlled_prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = db.relationship('ControlledPrescriptionItem', backref='controlled_prescription', lazy=True, cascade='all, delete-orphan')
    patient = db.relationship('Patient', backref='controlled_prescriptions')
    doctor = db.relationship('User', backref='controlled_prescriptions')


class ControlledPrescriptionItem(db.Model):
    __tablename__ = 'controlled_prescription_items'

    id = db.Column(db.Integer, primary_key=True)
    controlled_prescription_id = db.Column(db.Integer, db.ForeignKey('controlled_prescriptions.id'), nullable=False)
    controlled_drug_id = db.Column(db.Integer, db.ForeignKey('controlled_drugs.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    dosage = db.Column(db.Text)
    frequency = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    controlled_drug = db.relationship('ControlledDrug', backref='controlled_prescription_items')


class ControlledSale(db.Model):
    __tablename__ = 'controlled_sales'

    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(80), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pharmacist_name = db.Column(db.String(100))
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    patient = db.relationship('Patient', backref='controlled_sales')
    user = db.relationship('User', foreign_keys=[user_id], backref='controlled_sales')
    items = db.relationship('ControlledSaleItem', back_populates='sale', lazy=True, cascade='all, delete-orphan')


class ControlledSaleItem(db.Model):
    __tablename__ = 'controlled_sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('controlled_sales.id'), nullable=False)
    controlled_drug_id = db.Column(db.Integer, db.ForeignKey('controlled_drugs.id'), nullable=False)
    controlled_drug_name = db.Column(db.String(255))
    controlled_drug_specification = db.Column(db.Text)
    individual_sale_number = db.Column(db.String(120))
    description = db.Column(db.String(255), nullable=False, default='Controlled drug sale')
    prescription_source = db.Column(db.String(20), nullable=False, default='external')  # internal, external
    prescription_sheet_path = db.Column(db.String(500))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    controlled_drug = db.relationship('ControlledDrug', backref='controlled_sale_items')
    sale = db.relationship('ControlledSale', back_populates='items')

    def __init__(self, **kwargs):
        super(ControlledSaleItem, self).__init__(**kwargs)
        if getattr(self, 'controlled_drug', None):
            self.controlled_drug_name = self.controlled_drug.name
            self.controlled_drug_specification = self.controlled_drug.specification
    
class DrugDosage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    indication = db.Column(db.Text)
    contraindication = db.Column(db.Text)
    interaction = db.Column(db.Text)
    side_effects = db.Column(db.Text)
    dosage_peds = db.Column(db.Text)
    dosage_adults = db.Column(db.Text)
    dosage_geriatrics = db.Column(db.Text)
    important_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    drug = db.relationship('Drug', backref='dosage')


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    op_number = db.Column(db.String(500), unique=True, nullable=True)  # Increased from 20
    ip_number = db.Column(db.String(500), unique=True, nullable=True)  # Increased from 20
    name = db.Column(db.Text, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(200), nullable=True)  # Increased from 10
    address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.Text, nullable=True)
    destination = db.Column(db.Text, nullable=True)
    occupation = db.Column(db.Text, nullable=True)
    religion = db.Column(db.String(500), nullable=True)
    nok_name = db.Column(db.Text, nullable=True)
    nok_contact = db.Column(db.Text, nullable=True)
    tca = db.Column(db.Date, nullable=True)
    date_of_admission = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(250), default='active', nullable=True)
    chief_complaint = db.Column(db.Text, nullable=True)
    history_present_illness = db.Column(db.Text, nullable=True)
    
    # AI Integration Fields
    ai_assistance_enabled = db.Column(db.Boolean, default=False)
    ai_diagnosis = db.Column(db.Text)
    ai_treatment_recommendations = db.Column(db.Text)
    ai_last_updated = db.Column(db.DateTime)
    ai_confidence_score = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reviews = db.relationship('PatientReviewSystem', backref='patient', lazy=True)
    histories = db.relationship('PatientHistory', backref='patient', lazy=True)
    examinations = db.relationship('PatientExamination', backref='patient', lazy=True)
    diagnoses = db.relationship('PatientDiagnosis', backref='patient', lazy=True)
    management = db.relationship('PatientManagement', backref='patient', lazy=True)
    lab_requests = db.relationship('LabRequest', backref='patient', lazy=True)
    imaging_requests = db.relationship('ImagingRequest', backref='patient', lazy=True)
    summaries = db.relationship('PatientSummary', back_populates='patient', lazy=True)

    # Use methods instead of properties for decrypted data
    def get_decrypted_name(self):
        if not self.name:
            return None
        try:
            return Config.decrypt_data_static(self.name)
        except Exception:
            return "[Decryption Error]"

    def get_decrypted_address(self):
        if not self.address:
            return None
        try:
            return Config.decrypt_data_static(self.address)
        except Exception:
            return "[Decryption Error]"

    def get_decrypted_phone(self):
        if not self.phone:
            return None
        try:
            return Config.decrypt_data_static(self.phone)
        except Exception:
            return "[Decryption Error]"

    def get_decrypted_occupation(self):
        if not self.occupation:
            return None
        try:
            return Config.decrypt_data_static(self.occupation)
        except Exception:
            return "[Decryption Error]"

    def get_decrypted_nok_name(self):
        if not self.nok_name:
            return None
        try:
            return Config.decrypt_data_static(self.nok_name)
        except Exception:
            return "[Decryption Error]"

    def get_decrypted_nok_contact(self):
        if not self.nok_contact:
            return None
        try:
            return Config.decrypt_data_static(self.nok_contact)
        except Exception:
            return "[Decryption Error]"
    
    def get_ai_recommendations(self):
        """Return formatted AI recommendations if available"""
        if not self.ai_assistance_enabled or not self.ai_diagnosis:
            return None
        
        return {
            'diagnosis': self.ai_diagnosis,
            'treatment': self.ai_treatment_recommendations,
            'last_updated': self.ai_last_updated.strftime('%Y-%m-%d %H:%M') if self.ai_last_updated else None,
            'confidence': f"{round(self.ai_confidence_score * 100, 1)}%" if self.ai_confidence_score else None
        }
    
    def get_ai_summary(self):
        """Generate a concise summary of AI findings"""
        if not self.ai_assistance_enabled:
            return "AI assistance not enabled for this patient"
        
        summary = []
        if self.ai_diagnosis:
            summary.append(f"AI Diagnosis: {self.ai_diagnosis.splitlines()[0]}")
        if self.ai_treatment_recommendations:
            summary.append(f"Treatment Suggestions: {self.ai_treatment_recommendations.splitlines()[0]}")
        if self.ai_confidence_score:
            summary.append(f"Confidence: {round(self.ai_confidence_score * 100, 1)}%")
        
        return "\n".join(summary) if summary else "No AI recommendations available"

    
class PatientReviewSystem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    cns = db.Column(db.Text)
    cvs = db.Column(db.Text)
    rs = db.Column(db.Text)
    git = db.Column(db.Text)
    gut = db.Column(db.Text)
    skin = db.Column(db.Text)
    msk = db.Column(db.Text)
    
    # AI fields
    ai_suggested_questions = db.Column(db.Text)  # Stores AI-generated questions for review of systems
    ai_last_updated = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PatientHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    social_history = db.Column(db.Text)
    medical_history = db.Column(db.Text)
    surgical_history = db.Column(db.Text)
    family_history = db.Column(db.Text)
    allergies = db.Column(db.Text)
    medications = db.Column(db.Text)
    
    # AI fields
    ai_identified_risk_factors = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientExamination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    general_appearance = db.Column(db.Text)
    jaundice = db.Column(db.Boolean, default=False)
    pallor = db.Column(db.Boolean, default=False)
    cyanosis = db.Column(db.Boolean, default=False)
    lymphadenopathy = db.Column(db.Boolean, default=False)
    edema = db.Column(db.Boolean, default=False)
    dehydration = db.Column(db.Boolean, default=False)
    dehydration_parameters = db.Column(db.Text)
    temperature = db.Column(db.Float)
    pulse = db.Column(db.Integer)
    resp_rate = db.Column(db.Integer)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    spo2 = db.Column(db.Integer)
    weight = db.Column(db.Float)
    height = db.Column(db.Float)
    bmi = db.Column(db.Float)
    cvs_exam = db.Column(db.Text)
    resp_exam = db.Column(db.Text)
    abdo_exam = db.Column(db.Text)
    cns_exam = db.Column(db.Text)
    msk_exam = db.Column(db.Text)
    skin_exam = db.Column(db.Text)
    
    # AI fields
    ai_identified_red_flags = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    summary_type = db.Column(db.String(20), default='manual')  # 'manual' or 'ai_generated'
    generated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # FIXED: Use back_populates instead of backref to avoid naming conflicts
    patient = db.relationship('Patient', back_populates='summaries')
    generator = db.relationship('User', back_populates='generated_summaries')
    
class PatientDiagnosis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    working_diagnosis = db.Column(db.Text)
    differential_diagnosis = db.Column(db.Text)
    
        # AI fields
    ai_supported_diagnosis = db.Column(db.Boolean, default=False)
    ai_alternative_diagnoses = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    treatment_plan = db.Column(db.Text)
    follow_up = db.Column(db.Text)
    notes = db.Column(db.Text)   
     
    # AI fields
    ai_generated_plan = db.Column(db.Boolean, default=False)
    ai_alternative_treatments = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class LabRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships for template access
    test = db.relationship('LabTest', backref='lab_requests')
    requester = db.relationship('User', backref='created_lab_requests')

class ImagingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('imaging_test.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships for template access
    test = db.relationship('ImagingTest', backref='imaging_requests')
    requester = db.relationship('User', backref='created_imaging_requests')

class ImagingTest(db.Model):
    """Model for imaging tests available in the clinic"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ImagingTest {self.name}>'

class LabRequestItem(db.Model):
    """Model for individual items in a lab request"""
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('lab_request.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    results = db.Column(db.Text)
    comments = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    performed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    test = db.relationship('LabTest', backref='request_items')
    performer = db.relationship('User', backref='performed_lab_tests')

    def __repr__(self):
        return f'<LabRequestItem {self.id} for test {self.test_id}>'

class LabTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientLab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    results = db.Column(db.Text)
    comments = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        
    patient = db.relationship('Patient', backref='labs')
    test = db.relationship('LabTest', backref='patient_labs')
    performer = db.relationship('User', foreign_keys=[performed_by])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

# New model for examination findings
class ExaminationFinding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', back_populates='examination_findings')

# Update Patient model to include relationship
Patient.examination_findings = db.relationship('ExaminationFinding', back_populates='patient', lazy=True)

# Enhanced AIService class with more comprehensive AI integration
class AIService:
    
    MODELS = {
        'primary': 'deepseek-chat',  # Update based on verification
        'fallback': 'gpt-3.5-turbo'  # Optional fallback
    }

    @classmethod
    def get_client(cls):
        """Get AI client with proper configuration"""
        api_key = current_app.config.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        
        return OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30.0
        )
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=(retry_if_exception_type(APITimeoutError) | 
              retry_if_exception_type(APIError)),
        reraise=True
    )
    
    @staticmethod
    def generate_review_systems_questions(patient_data):
        """Generate focused review of systems questions based on chief complaint and biodata"""
        prompt = f"""
        As an experienced physician, suggest the most relevant review of systems questions for this patient:
        
        Patient: {patient_data.get('age')}
        Patient: {patient_data.get('address', 'Not specified')}
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Chief Complaint: {patient_data['chief_complaint']}
        Occupation: {patient_data.get('occupation', 'Not specified')}
        
        Provide:
        1. 3-5 most relevant systems to review based on the chief complaint
        2. 2-3 specific questions for each relevant system
        3. Format as a bulleted list with clear system headings
        
        Focus on questions that would help identify important positives/negatives basing on the most likeley differentials diagnosis according to patient data in age, gender, occupation, address and chief complain.
        """
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",  # Changed from "deepseek-medical"
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Review Systems Error: {str(e)}")
            return None

    @staticmethod
    def generate_hpi_questions(patient_data):
        """Generate HPI questions using SOCRATES framework with retries and fallbacks"""
        prompt = AIService._build_hpi_prompt(patient_data)
        
        for model_name in AIService.MODELS.values():
            try:
                response = AIService.get_client().chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.warning(f"Model {model_name} failed: {str(e)}")
                continue
                
        return None

    @staticmethod
    def log_ai_error(method_name, error, patient_data=None):
        """Centralized error logging"""
        error_info = {
            "error": str(error),
            "type": type(error).__name__,
            "patient_data": patient_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        current_app.logger.error(
            f"AI {method_name} Error",
            extra={"error_details": error_info},
            exc_info=True
        )
        
    @staticmethod
    def generate_hpi_content(patient_data):
        """Robust HPI generation with model verification"""
        prompt = AIService._build_hpi_prompt(patient_data)
        
        for model_name in AIService.MODELS.values():
            try:
                response = AIService.get_client().chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800,
                    timeout=60  # Reduced timeout for individual requests
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.warning(f"Model {model_name} failed: {str(e)}")
                continue
                
        return None

    @staticmethod
    def _build_hpi_prompt(patient_data):
        """Construct a detailed HPI prompt with proper validation and structure
        
        Args:
            patient_data (dict): Dictionary containing patient information including:
                - age
                - gender
                - address 
                - occupation
                - chief_complaint
                - review_of_systems
        
        Returns:
            str: A well-structured prompt for AI-generated HPI content
        """
     
        age = patient_data.get('age', 'unknown age')
        gender = patient_data.get('gender', 'unknown gender')
        address = patient_data.get('address', 'address not specified')
        occupation = patient_data.get('occupation', 'occupation not specified')
        chief_complaint = patient_data.get('chief_complaint', 'unspecified complaint')
        review_systems = patient_data.get('review_systems', 'not documented')
        
        return f"""
        As an experienced physician, generate a comprehensive History of Present Illness (HPI) 
        for this patient case following the SOCRATES framework and including all relevant details:

        Patient Background:
        - age: {age} 
        - gender {gender}
        - address: {address}
        - Occupation: {occupation}
        - Chief Complaint: "{chief_complaint}"
        - Review of Systems: {review_systems}

        Required HPI Structure:
        1. Opening Statement:
        - Start with a concise opening that introduces the patient and chief complaint

        2. Symptom Analysis (SOCRATES):
        a) Site: Location of symptoms with radiation patterns
        b) Onset: When it began and circumstances of onset
        c) Character: Quality and nature of symptoms
        d) Radiation: Where symptoms spread/migrate
        e) Associated Symptoms: Other related symptoms
        f) Time Course: Progression since onset
        g) Exacerbating/Relieving Factors: What makes it better/worse
        h) Severity: Quantitative measure (e.g., pain scale)

        3. Contextual Factors:
        - Impact on daily activities and work
        - Any previous treatments attempted and their effects
        - Relevant psychosocial factors
        - Occupational exposures or risk factors

        4. Summary:
        - Brief synthesis of key findings
        - Any red flags or urgent concerns

        Additional Instructions:
        - Use professional medical terminology but keep it clear
        - Organize information logically
        - Include pertinent positives and negatives
        - For pain complaints, use the OPQRST mnemonic if applicable
        - Highlight any findings that suggest urgent evaluation

        Please generate the HPI in full paragraph narrative format suitable for a medical record.
        """

    def generate_patient_summary(patient_data):
        """
        Generate a comprehensive patient summary from all available patient data
        """
        prompt = f"""
        You are an experienced medical professional. Create a comprehensive patient summary 
        by synthesizing all the available patient information into a coherent clinical narrative.
        
        PATIENT INFORMATION:
        
        Biodata:
        - Name: {patient_data.get('name', 'Not specified')}
        - Age: {patient_data.get('age', 'Not specified')}
        - Gender: {patient_data.get('gender', 'Not specified')}
        - Address: {patient_data.get('address', 'Not specified')}
        - Occupation: {patient_data.get('occupation', 'Not specified')}
        - Religion: {patient_data.get('religion', 'Not specified')}
        
        Chief Complaint:
        {patient_data.get('chief_complaint', 'Not documented')}
        
        History of Present Illness (HPI):
        {patient_data.get('history_present_illness', 'Not documented')}
        
        Review of Systems (ROS):
        {json.dumps(patient_data.get('review_systems', {}), indent=2)}
        
        Medical History:
        - Social History: {patient_data.get('social_history', 'Not documented')}
        - Medical History: {patient_data.get('medical_history', 'Not documented')}
        - Surgical History: {patient_data.get('surgical_history', 'Not documented')}
        - Family History: {patient_data.get('family_history', 'Not documented')}
        - Allergies: {patient_data.get('allergies', 'None known')}
        - Current Medications: {patient_data.get('medications', 'None')}
        
        Physical Examination Findings:
        {json.dumps(patient_data.get('examination', {}), indent=2)}
        
        Current Working Diagnosis:
        {patient_data.get('working_diagnosis', 'Not established')}
        
        Please create a well-structured patient summary that includes:
        1. Patient demographics and presenting complaint
        2. Key findings from history and examination
        3. Assessment and current diagnosis
        4. Relevant positive and negative findings
        5. Clinical impression
        
        Format the summary in professional medical narrative style, suitable for inclusion in a medical record.
        Be concise but comprehensive, focusing on clinically relevant information.
        """
        
        try:
            client = AIService.get_client()
            response = client.chat.completions.create(
                model=AIService.MODELS['primary'],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200,
                timeout=30
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Summary Generation Error: {str(e)}")
            return None

    @staticmethod
    def generate_diagnosis_from_summary(clinical_summary, patient_info=None):
        """
        Generate differential diagnosis based on clinical summary
        """
        try:
            # Use the client that's already initialized in the class
            client = AIService.get_client()
            model = AIService.MODELS['primary']
            
            # Build patient context
            patient_context = ""
            if patient_info:
                if patient_info.get('age'):
                    patient_context += f"Age: {patient_info['age']} years\n"
                if patient_info.get('gender'):
                    patient_context += f"Gender: {patient_info['gender']}\n"
                if patient_info.get('name'):
                    patient_context += f"Patient: {patient_info['name']}\n"
            
            prompt = f"""
            As an experienced medical diagnostician, analyze the following clinical summary and provide a comprehensive differential diagnosis.

            PATIENT CONTEXT:
            {patient_context}

            CLINICAL SUMMARY:
            {clinical_summary}

            Please provide a structured analysis with the following sections:

            1. PRIMARY WORKING DIAGNOSIS:
            - The most likely diagnosis based on the clinical presentation
            - Brief rationale explaining why this is the most likely

            2. DIFFERENTIAL DIAGNOSES (List 3-5 alternatives in order of likelihood):
            For each differential diagnosis include:
            - Condition name
            - Key supporting features from the clinical summary
            - Important distinguishing features from the working diagnosis

            3. KEY CLINICAL FINDINGS:
            - List the most significant positive findings from the summary
            - Note any important negative findings that help rule out alternatives

            4. RECOMMENDED INVESTIGATIONS:
            - Essential tests to confirm the working diagnosis
            - Tests to rule out key differential diagnoses
            - Any urgent investigations if red flags are present

            5. CLINICAL PEARLS:
            - Important considerations for management
            - Any red flags or urgent concerns
            - Specific follow-up recommendations

            Format your response in clear, clinical language suitable for medical records.
            Be concise but comprehensive.
            """
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Diagnosis from Summary Error: {str(e)}")
            return None


    # Keep your existing methods but update the main diagnosis method to use summary
    @staticmethod
    def generate_diagnosis(patient_data):
        """
        Updated to prioritize clinical summary if available
        """
        # Check if clinical summary is available in patient_data
        clinical_summary = patient_data.get('clinical_summary') or patient_data.get('patient_summary')
        
        if clinical_summary:
            # Use the summary-based diagnosis
            patient_info = {
                'age': patient_data.get('age'),
                'gender': patient_data.get('gender'),
                'name': patient_data.get('name')
            }
            return AIService.generate_diagnosis_from_summary(clinical_summary, patient_info)
        else:
            # Fall back to the original detailed diagnosis method
            return AIService._generate_detailed_diagnosis(patient_data)

    @staticmethod
    def _generate_detailed_diagnosis(patient_data):
        """
        Original detailed diagnosis method (fallback)
        """
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Based on the following patient information, generate a differential diagnosis:
            
            Patient Demographics:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            
            Clinical Presentation:
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            - History of Present Illness: {patient_data.get('history_present_illness', 'Not documented')}
            
            Review of Systems:
            {json.dumps(patient_data.get('review_systems', {}), indent=2)}
            
            Medical History:
            - Social: {patient_data.get('social_history', 'Not documented')}
            - Medical: {patient_data.get('medical_history', 'Not documented')}
            - Surgical: {patient_data.get('surgical_history', 'Not documented')}
            - Family: {patient_data.get('family_history', 'Not documented')}
            - Allergies: {patient_data.get('allergies', 'None known')}
            - Medications: {patient_data.get('medications', 'None')}
            
            Physical Examination:
            {json.dumps(patient_data.get('examination', {}), indent=2)}
            
            Please provide:
            1. Most likely diagnosis (working diagnosis)
            2. 3-5 differential diagnoses in order of likelihood
            3. Brief rationale for each
            4. Suggested diagnostic tests to confirm
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Diagnosis Error: {str(e)}")
            return None
        
    @staticmethod
    def generate_treatment_plan(patient_data, available_drugs):
        """
        Generate comprehensive treatment plan considering available drugs
        """
        drugs_list = "\n".join([f"- {drug.name} ({drug.specification})" for drug in available_drugs])
        
        prompt = f"""
        Create a treatment plan for this patient considering available medications:
        
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Diagnosis: {patient_data['diagnosis']}
        Allergies: {patient_data.get('allergies', 'None known')}
        Current Medications: {patient_data.get('medications', 'None')}
        
        Available Drugs:
        {drugs_list}
        
        Provide:
        1. First-line treatment recommendations using available drugs
        2. Alternative options if first-line isn't available
        3. Specific dosages based on patient factors
        4. Duration of treatment
        5. Monitoring recommendations
        6. Patient education points
        7. Follow-up plan
        """
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-medical",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Treatment Plan Error: {str(e)}")
            return None

class DebtPayment(db.Model):
    __tablename__ = 'debt_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    debtor_id = db.Column(db.Integer, db.ForeignKey('debts.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Added this line
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='debt_payments')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
  
    items = db.relationship('PrescriptionItem', backref='prescription', lazy=True)  
    patient = db.relationship('Patient', backref='prescriptions')
    doctor = db.relationship('User', backref='prescriptions')

class PrescriptionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    dosage = db.Column(db.Text)
    frequency = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    drug = db.relationship('Drug', backref='prescription_items')

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(50), unique=True, nullable=False)
    bulk_sale_number = db.Column(db.String(20))
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pharmacist_name = db.Column(db.String(100))  # Store pharmacist name directly
    total_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = db.relationship('Patient', backref='patient_sales')
    user = db.relationship('User', foreign_keys=[user_id], backref='user_sales')
    items = db.relationship('SaleItem', back_populates='sale', lazy=True, cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    drug_name = db.Column(db.String(100))  # Store drug name directly
    drug_specification = db.Column(db.String(200))  # Store drug specs
    individual_sale_number = db.Column(db.String(100))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    lab_test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'))
    description = db.Column(db.String(200), nullable=False, default="Drug sale")
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    drug = db.relationship('Drug', backref='sale_items')
    service = db.relationship('Service', backref='sale_items')
    lab_test = db.relationship('LabTest', backref='sale_items')
    sale = db.relationship('Sale', back_populates='items')

    def __init__(self, **kwargs):
        super(SaleItem, self).__init__(**kwargs)
        # Automatically set drug info when drug is assigned
        if self.drug:
            self.drug_name = self.drug.name
            self.drug_specification = self.drug.specification

class Refund(db.Model):
    __tablename__ = 'refunds'
    
    id = db.Column(db.Integer, primary_key=True)
    refund_number = db.Column(db.String(50), unique=True, nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='completed')
    
    # Relationships
    sale = db.relationship('Sale', backref='refunds')
    user = db.relationship('User', backref='refunds')
    items = db.relationship('RefundItem', back_populates='refund')

class RefundItem(db.Model):
    __tablename__ = 'refund_items'  # Note the correct table name
    
    id = db.Column(db.Integer, primary_key=True)
    refund_id = db.Column(db.Integer, db.ForeignKey('refunds.id'), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Relationships
    refund = db.relationship('Refund', back_populates='items')
    sale_item = db.relationship('SaleItem', backref='refund_items')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # sale, refund, payment, expense, etc.
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reference_id = db.Column(db.Integer)  # ID of related record (sale, expense, etc.)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='transactions')

def generate_transaction_number():
    return f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    purpose = db.Column(db.String(200))
    status = db.Column(db.String(20), default='scheduled')  # scheduled, confirmed, cancelled, completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('User', backref='appointments')

class Debt(db.Model):
    __tablename__ = 'debts'
    
    id = db.Column(db.Integer, primary_key=True)
    debt_number = db.Column(db.String(50), unique=True, nullable=False)
    debt_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    creditor = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date)
    interest_rate = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payments = db.relationship('DebtPayment', backref='debt', lazy=True)


def generate_debt_number():
    return f"DEBT-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, nullable=False)
    expense_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='paid')  # paid, pending, cancelled
    paid_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='expenses')

def generate_expense_number():
    return f"EXP-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(50), unique=True, nullable=False)
    purchase_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

def generate_purchase_number():
    return f"PUR-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    salary = db.Column(db.Float)
    hire_date = db.Column(db.Date)
    contact = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payrolls = db.relationship('Payroll', backref='employee', lazy=True)
    user = db.relationship('User', backref='employee')


class Payroll(db.Model):
    __tablename__ = 'payrolls'
    
    id = db.Column(db.Integer, primary_key=True)
    payroll_number = db.Column(db.String(50), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    pay_period = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def generate_payroll_number():
    return f"PAY-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Debtor(db.Model):
    __tablename__ = 'debtor'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    email = db.Column(db.String(100))
    Total_debt = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    amount_owed = db.Column(db.Float, default=0.0)
    last_payment_date = db.Column(db.Date)
    next_payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    payments = db.relationship('DebtorPayment', backref='debtor', lazy=True)


class PayrollPayment(db.Model):
    __tablename__ = 'payroll_payments'

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.Integer, db.ForeignKey('payrolls.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    payment_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text)

    payroll = db.relationship('Payroll', backref=db.backref('payments', lazy=True))
    user = db.relationship('User', backref='payroll_payments')

class DebtorPayment(db.Model):
    __tablename__ = 'debtor_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    debtor_id = db.Column(db.Integer, db.ForeignKey('debtor.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    notes = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='services')
    service = db.relationship('Service', backref='patient_services')
    performer = db.relationship('User', foreign_keys=[performed_by])


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    table_name = db.Column(db.String(50))  # Tracks which table was affected
    record_id = db.Column(db.Integer)      # ID of the affected record
    description = db.Column(db.String(255))  # For backward compatibility
    changes = db.Column(db.JSON)           # Structured change data
    old_values = db.Column(db.JSON)        # Previous values before change
    new_values = db.Column(db.JSON)        # Values after change
    ip_address = db.Column(db.String(50))  # IP address of the requester
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


    # Relationship
    user = db.relationship('User', backref='audit_log_entries')

    def __init__(self, **kwargs):
        if 'description' not in kwargs and 'changes' in kwargs:
            kwargs['description'] = str(kwargs.get('changes'))
        super().__init__(**kwargs)

    def to_dict(self):
        """Returns audit log entry as dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'table_name': self.table_name,
            'record_id': self.record_id,
            'description': self.description,
            'changes': self.changes,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user': {
                'id': self.user.id,
                'username': self.user.username
            } if self.user else None
        }

def generate_random_string(length=6):
    """Helper function to generate random strings"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# ==================== REPORTING ENHANCEMENT MODELS ====================

class ReportAuditLog(db.Model):
    """Logs all report generation for compliance and audit trails"""
    __tablename__ = 'report_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)  # drug_sales, patients, department, etc
    filters = db.Column(db.JSON)  # {"start_date": "2026-01-01", "end_date": "2026-01-03", "granularity": "daily", ...}
    data_count = db.Column(db.Integer)  # Number of records in report
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(50))
    status = db.Column(db.String(20), default='success')  # success, error, timeout
    error_message = db.Column(db.Text)  # If status is error
    
    user = db.relationship('User', backref='report_audits')


class DepartmentBudget(db.Model):
    """Tracks budgets per department for variance analysis"""
    __tablename__ = 'department_budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=False, unique=True)
    fiscal_year = db.Column(db.Integer, nullable=False)
    budgeted_amount = db.Column(db.Float, nullable=False)
    actual_amount = db.Column(db.Float, default=0)
    variance = db.Column(db.Float, default=0)  # actual - budgeted
    variance_percentage = db.Column(db.Float, default=0)  # variance / budgeted * 100
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PatientSegment(db.Model):
    """Patient segmentation for analytics (insurance type, VIP status, etc)"""
    __tablename__ = 'patient_segments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, unique=True)
    insurance_type = db.Column(db.String(50))  # NHIF, private, uninsured, corporate, etc
    vip_status = db.Column(db.Boolean, default=False)
    referral_source = db.Column(db.String(100))  # Self, referral, insurance, etc
    patient_lifetime_value = db.Column(db.Float, default=0)  # Total spent lifetime
    visit_frequency = db.Column(db.Integer, default=0)  # Number of visits
    average_transaction = db.Column(db.Float, default=0)  # Average amount per visit
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='segment')


class ProviderPerformance(db.Model):
    """Tracks provider (doctor) performance metrics"""
    __tablename__ = 'provider_performance'
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fiscal_period = db.Column(db.String(20), nullable=False)  # YYYY-MM or YYYY-Wnn
    patients_seen = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0)
    average_patient_value = db.Column(db.Float, default=0)
    procedures_completed = db.Column(db.Integer, default=0)
    readmission_count = db.Column(db.Integer, default=0)
    satisfaction_score = db.Column(db.Float)  # 1-5 scale
    quality_score = db.Column(db.Float)  # Composite quality metric
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    provider = db.relationship('User', backref='performance_metrics')


class QualityMetric(db.Model):
    """Clinical quality metrics (readmission, mortality, outcomes)"""
    __tablename__ = 'quality_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    admission_date = db.Column(db.DateTime, nullable=False)
    discharge_date = db.Column(db.DateTime)
    discharge_status = db.Column(db.String(20))  # discharged, died, referred, absconded
    length_of_stay = db.Column(db.Integer)  # days
    readmitted_within_30d = db.Column(db.Boolean, default=False)
    readmission_date = db.Column(db.DateTime)
    primary_diagnosis = db.Column(db.String(200))
    adverse_events = db.Column(db.Integer, default=0)  # Count of adverse events
    infections_acquired = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='quality_metrics')


# ==================== END REPORTING MODELS ====================

# Replace with this:
_first_request = True
from flask import current_app

_first_request = True

# Replace with this:
_first_request = True

@app.before_request
def initialize_data():
    global _first_request
    if not _first_request:
        return
    _first_request = False
    
    # Use application context
    with app.app_context():
        try:
            # Create all database tables
            db.create_all()

            # Create default admin if not exists
            admin_exists = db.session.execute(
                db.select(User).filter_by(role='admin')
            ).scalar()
            
            if not admin_exists:
                admin = User(
                    username='Makokha Nelson',
                    email='makokhanelson4@gmail.com',
                    role='admin',
                    is_active=True
                )
                admin.set_password('Doc.makokha@2024')
                db.session.add(admin)
            
            # Create default doctor if not exists
            doctor_exists = db.session.execute(
                db.select(User).filter_by(role='doctor')
            ).scalar()
            
            if not doctor_exists:
                doctor = User(
                    username='Default Doctor',
                    email='doctor@clinic.com',
                    role='doctor',
                    is_active=True
                )
                doctor.set_password('Doctor@123')
                db.session.add(doctor)
            
            # Create default pharmacist if not exists
            pharmacist_exists = db.session.execute(
                db.select(User).filter_by(role='pharmacist')
            ).scalar()
            
            if not pharmacist_exists:
                pharmacist = User(
                    username='Default Pharmacist',
                    email='pharmacist@clinic.com',
                    role='pharmacist',
                    is_active=True
                )
                pharmacist.set_password('Pharmacist@123')
                db.session.add(pharmacist)
            
            # Create default receptionist if not exists
            receptionist_exists = db.session.execute(
                db.select(User).filter_by(role='receptionist')
            ).scalar()
            
            if not receptionist_exists:
                receptionist = User(
                    username='Default Receptionist',
                    email='receptionist@clinic.com',
                    role='receptionist',
                    is_active=True
                )
                receptionist.set_password('Receptionist@123')
                db.session.add(receptionist)
            
            # Commit all changes at once
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error initializing data: {str(e)}")
            
# Login ManagerT
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Audit logging function
def log_audit(action, table=None, record_id=None, user_id=None, changes=None, 
             old_values=None, new_values=None, ip_address=None):
    """
    Logs an audit trail entry with comprehensive tracking
    
    Args:
        action (str): The action performed (e.g., 'create', 'update', 'delete')
        table (str): Name of the database table affected
        record_id: ID of the affected record
        user_id: ID of the user performing the action
        changes (dict): Summary of changes made (for complex operations)
        old_values: Previous values before change (for updates)
        new_values: New values after change (for updates)
        ip_address: IP address of the requester
    """
    try:
        user_id = user_id if user_id is not None else (
            current_user.id if current_user.is_authenticated else None
        )
        
        ip_address = ip_address if ip_address is not None else request.remote_addr
        
        changes_data = None
        if changes:
            changes_data = json.dumps(changes, default=str)
        elif new_values is not None:
            changes_data = json.dumps({'new_values': new_values}, default=str)
        
        log = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table,
            record_id=record_id,
            changes=changes_data,
            old_values=str(old_values) if old_values else None,
            new_values=str(new_values) if new_values else None,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)  # Changed from timestamp
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to log audit trail: {str(e)}")

# Admin JSON decorator and helpers

def admin_required_json(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return wrapper


def parse_price(value):
    try:
        amount = Decimal(str(value))
        if amount < 0:
            return None, 'Price must be non-negative'
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return amount, None
    except (InvalidOperation, TypeError):
        return None, 'Invalid price'


def parse_bool(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'on', 'yes')


def bad_request(message):
    return jsonify({'success': False, 'error': message}), 400


def success_response(data=None, status=200):
    payload = {'success': True}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status

# Utility functions
def generate_patient_number(patient_type):
    prefix = 'OP' if patient_type == 'OP' else 'IP'
    last_patient = Patient.query.filter(
        Patient.op_number.isnot(None) if patient_type == 'OP' else Patient.ip_number.isnot(None)
    ).order_by(Patient.id.desc()).first()
    
    if last_patient:
        last_number = last_patient.op_number if patient_type == 'OP' else last_patient.ip_number
        last_seq = int(last_number.split('MNC')[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    
    return f"{prefix}MNC{new_seq:03d}"

def generate_sale_number():
    now = datetime.now()
    return f"SALE-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

def generate_bulk_sale_number():
    now = datetime.now()
    return f"BULK-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

def generate_individual_sale_number():
    now = datetime.now()
    return f"ITEM-{now.strftime('%Y%m%d')}-{random.randint(100, 999)}"

def database_is_sqlite():
    try:
        inspector = inspect(db.engine)
        return inspector.dialect.name == 'sqlite'
    except:
        return False

def database_is_postgresql():
    try:
        inspector = inspect(db.engine)
        return inspector.dialect.name == 'postgresql'
    except:
        return False

def get_database_dialect():
    try:
        inspector = inspect(db.engine)
        return inspector.dialect.name
    except:
        return 'unknown'
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        elif current_user.role == 'pharmacist':
            return redirect(url_for('pharmacist_dashboard'))
        elif current_user.role == 'receptionist':
            return redirect(url_for('receptionist_dashboard'))
    return redirect(url_for('auth.login'))
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # ...existing code for saving patient...
        db.session.commit()
        flash('Patient saved successfully!', 'success')
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                os.makedirs(PROFILE_PICTURE_FOLDER, exist_ok=True)
                filename = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                filename = f"user_{current_user.id}_{timestamp}_{filename}"
                filepath = os.path.join(PROFILE_PICTURE_FOLDER, filename)
                file.save(filepath)
                if current_user.profile_picture:
                    old_path = os.path.join(app.root_path, 'static', current_user.profile_picture)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            app.logger.error(f"Error deleting old profile picture: {str(e)}")

                current_user.profile_picture = os.path.join('uploads', 'profile_pictures', filename).replace('\\', '/')

        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)
        
        new_password = request.form.get('new_password')
        if new_password:
            if check_password_hash(current_user.password, request.form.get('current_password')):
                current_user.set_password(new_password)
                flash('Password updated successfully!', 'success')
            else:
                flash('Current password is incorrect', 'danger')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=current_user)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}



@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter((User.email == email) | (User.username == email)).first()
        
        if user and user.check_password(password) and user.is_active and user.role == role:
            login_user(user, remember=remember)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        
        flash('Invalid credentials or role', 'danger')
    
    return render_template('auth/login.html')

@app.context_processor
def inject_current_date():
    return {'current_date': date.today().strftime('%Y-%m-%d')}

@app.context_processor
def inject_csrf_token():
    """Expose csrf_token() in all Jinja templates"""
    return dict(csrf_token=generate_csrf)
@app.route('/logout')
@login_required
def logout():
    log_audit('logout')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))  # Changed from 'login' to 'auth.login'


def send_async_email(app, msg):
    """Send email asynchronously in a background thread."""
    with app.app_context():
        mail.send(msg)

def send_password_reset_email(user_email, token):
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    
    msg = Message(
        "Reset Your Password",
        recipients=[user_email],
        html=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2d3748;">Password Reset Request</h2>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_url}" 
               style="display: inline-block; padding: 10px 20px; 
                      background-color: #4299e1; color: white; 
                      text-decoration: none; border-radius: 4px;">
                Reset Password
            </a>
            <p style="margin-top: 20px; color: #718096;">
                This link expires in 1 hour. If you didn't request this, please ignore this email.
            </p>
        </div>
        """
    )
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

# Generate token
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

# Verify token
def verify_reset_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=max_age
        )
        return email
    except:
        return False
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_request():
    form = ResetPasswordRequestForm()  # Create form instance
    
    if form.validate_on_submit():  # Use validate_on_submit for proper form validation
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user.email)
            send_password_reset_email(user.email, token)
            flash('Password reset link sent to your email', 'info')
            return redirect(url_for('auth.login'))
        flash('Email not found', 'danger')
    
    # Pass the form to the template
    return render_template('auth/reset_request.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    email = verify_reset_token(token)
    if not email:
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('auth.reset_request'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.reset_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        user.set_password(password)  # Your password hashing method
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_token.html', token=token)
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_password():
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        
        if user:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
            reset_url = url_for('auth.reset_with_token', token=token, _external=True)
            
            if send_password_reset_email(email, reset_url):
                flash('A password reset link has been sent to your email.', 'info')
            else:
                flash('Failed to send email. Please try again later.', 'danger')
            return redirect(url_for('auth.login'))
        
        flash('If this email exists in our system, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset.html', form=form)

@auth_bp.route('/reset/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_with_token(token):
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=current_app.config['RESET_TOKEN_EXPIRATION']
        )
    except:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.reset_password'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid user.', 'danger')
        return redirect(url_for('auth.reset_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_with_token.html', form=form, token=token)



@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    try:
        total_drugs = db.session.query(func.count(Drug.id)).scalar()
        low_stock = db.session.query(func.count(Drug.id)).filter(
            Drug.stocked_quantity - Drug.sold_quantity < 10
        ).scalar()
        
        expiring_soon = db.session.query(func.count(Drug.id)).filter(
            Drug.expiry_date <= date.today() + timedelta(days=30)
        ).scalar()
        
        # Today's sales
        today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
            func.date(Sale.created_at) == date.today()
        ).scalar() or 0
        
        # UNIVERSAL FIX: Use extract for month and year - works on all databases
        current_date = datetime.now()
        monthly_sales = db.session.query(func.sum(Sale.total_amount)).filter(
            func.extract('year', Sale.created_at) == current_date.year,
            func.extract('month', Sale.created_at) == current_date.month
        ).scalar() or 0
        
        pending_bills = db.session.query(func.sum(Debtor.amount_owed)).scalar() or 0
        
        last_backup = BackupRecord.query.filter_by(status='completed')\
            .order_by(BackupRecord.timestamp.desc()).first()
        last_backup_time = last_backup.timestamp if last_backup else 'Never'
        
        backup_stats = {
            'total_backups': BackupRecord.query.count(),
            'successful_backups': BackupRecord.query.filter_by(status='completed').count(),
            'failed_backups': BackupRecord.query.filter_by(status='failed').count(),
            'total_size_mb': db.session.query(
                func.coalesce(func.sum(BackupRecord.size_bytes), 0) / (1024 * 1024)
            ).scalar()
        }
        
        active_users = db.session.query(func.count(User.id)).filter_by(is_active=True).scalar()
        
        # Get doctor statistics - ensure these are called
        daily_stats = get_doctor_stats('daily')
        monthly_stats = get_doctor_stats('monthly')
        yearly_stats = get_doctor_stats('yearly')
        
        # Get recent activity
        recent_activity = db.session.query(
            AuditLog.id,
            AuditLog.action,
            AuditLog.created_at.label('created_at'),
            literal('audit').label('type')
        ).union_all(
            db.session.query(
                BackupRecord.id,
                literal('backup').label('action'),
                BackupRecord.timestamp.label('created_at'),
                literal('backup').label('type')
            )
        ).order_by(text('created_at DESC')).limit(10).all()
        
        return render_template('admin/dashboard.html',
            total_drugs=total_drugs,
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            today_sales=today_sales,
            monthly_sales=monthly_sales,
            pending_bills=pending_bills,
            last_backup_time=last_backup_time,
            backup_stats=backup_stats,
            active_users=active_users,
            daily_stats=daily_stats,
            monthly_stats=monthly_stats,
            yearly_stats=yearly_stats,
            recent_activity=recent_activity
        )
    
    except Exception as e:
        app.logger.error(f"Error in admin dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('home'))

def get_total_beds():
    return Bed.query.count()

def get_available_beds():
    return Bed.query.filter_by(status='available').count()

def get_occupied_beds():
    return Bed.query.filter_by(status='occupied').count()

def get_doctor_stats(timeframe='daily'):
    """Get statistics for doctors based on timeframe (daily, monthly, yearly)"""
    today = date.today()
    
    if timeframe == 'daily':
        start_date = today
        end_date = today + timedelta(days=1)
    elif timeframe == 'monthly':
        start_date = date(today.year, today.month, 1)
        end_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
    elif timeframe == 'yearly':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year + 1, 1, 1)
    else:
        start_date = today
        end_date = today + timedelta(days=1)

    # Get inpatient and outpatient counts - using date comparisons compatible with PostgreSQL
    inpatients = db.session.query(Patient).filter(
        Patient.ip_number.isnot(None),
        Patient.date_of_admission >= start_date,
        Patient.date_of_admission < end_date
    ).count()

    outpatients = db.session.query(Patient).filter(
        Patient.op_number.isnot(None),
        Patient.date_of_admission >= start_date,
        Patient.date_of_admission < end_date
    ).count()

    # Get discharged patients - using date comparisons
    discharged = db.session.query(Patient).filter(
        Patient.status == 'completed',
        Patient.updated_at >= start_date,
        Patient.updated_at < end_date
    ).count()

    # Get bed statistics with zero division protection
    total_beds = get_total_beds()
    occupied_beds = get_occupied_beds()
    available_beds = get_available_beds()
    
    # Calculate occupancy rate with zero division protection
    occupancy_rate = 0
    if total_beds > 0:
        occupancy_rate = (occupied_beds / total_beds) * 100

    return {
        'inpatients': inpatients,
        'outpatients': outpatients,
        'discharged': discharged,
        'occupied_beds': occupied_beds,
        'available_beds': available_beds,
        'total_beds': total_beds,
        'occupancy_rate': occupancy_rate,
        'timeframe': timeframe,
        'start_date': start_date,
        'end_date': end_date - timedelta(days=1)  # Subtract 1 day to show inclusive end data
    }

# Backup utility functions
def create_backup(backup_id):
    """Create a database backup in background"""
    backup = BackupRecord.query.get(backup_id)
    if not backup:
        return
    
    try:
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        backup_file = os.path.join(temp_dir, f'backup_{backup.backup_id}.zip')
        
        # Create a ZIP file containing all table data as JSON
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Backup each table
            for table_name in BACKUP_CONFIG['tables_to_backup']:
                try:
                    # Get table data
                    result = db.engine.execute(text(f'SELECT * FROM {table_name}'))
                    rows = [dict(row) for row in result]
                    
                    # Convert to JSON
                    table_data = json.dumps(rows, indent=2, default=str)
                    
                    # Add to ZIP
                    zipf.writestr(f'{table_name}.json', table_data)
                except Exception as e:
                    app.logger.error(f'Error backing up table {table_name}: {str(e)}')
                    continue
            
            # Add metadata
            metadata = {
                'backup_id': backup.backup_id,
                'timestamp': get_eat_now().isoformat(),
                'database_url': str(db.engine.url),
                'tables_backed_up': BACKUP_CONFIG['tables_to_backup'],
                'app_version': '1.0.0'
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        # Calculate checksum
        with open(backup_file, 'rb') as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
            checksum = file_hash.hexdigest()
        
        # Encrypt the backup
        cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
        with open(backup_file, 'rb') as f:
            encrypted_data = cipher_suite.encrypt(f.read())
        
        encrypted_file = backup_file + '.enc'
        with open(encrypted_file, 'wb') as f:
            f.write(encrypted_data)
        
        # Get file size
        file_size = os.path.getsize(encrypted_file)
        
        # Store backup (local or S3)
        if s3_client:
            # Upload to S3
            s3_key = f'backups/{backup.backup_id}.zip.enc'
            s3_client.upload_file(
                encrypted_file,
                BACKUP_CONFIG['s3_bucket'],
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'backup-id': backup.backup_id,
                        'checksum': checksum,
                        'created-by': str(current_user.id)
                    }
                }
            )
            storage_location = f's3://{BACKUP_CONFIG["s3_bucket"]}/{s3_key}'
        else:
            # Store locally
            local_backup_dir = BACKUP_CONFIG['local_storage_path']
            os.makedirs(local_backup_dir, exist_ok=True)
            local_path = os.path.join(local_backup_dir, f'{backup.backup_id}.zip.enc')
            os.rename(encrypted_file, local_path)
            storage_location = local_path
        
        # Update backup record
        backup.status = 'completed'
        backup.size_bytes = file_size
        backup.storage_location = storage_location
        backup.checksum = checksum
        db.session.commit()
        
        # Clean up
        try:
            os.remove(backup_file)
            if os.path.exists(encrypted_file):
                os.remove(encrypted_file)
            os.rmdir(temp_dir)
        except:
            pass
        
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}', exc_info=True)
        backup.status = 'failed'
        backup.notes = f'Error: {str(e)}'
        db.session.commit()

@app.route('/admin/beds', methods=['GET', 'POST'])
@login_required
def manage_beds():
    # Simple admin check
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Rest of your function code remains the same
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_ward':
            try:
                ward = Ward(
                    name=request.form.get('ward_name'),
                    description=request.form.get('ward_description')
                )
                db.session.add(ward)
                db.session.commit()
                flash('Ward added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding ward: {str(e)}', 'danger')
        
        elif action == 'add_bed':
            try:
                bed = Bed(
                    bed_number=request.form.get('bed_number'),
                    ward_id=request.form.get('ward_id'),
                    status='available'
                )
                db.session.add(bed)
                db.session.commit()
                flash('Bed added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding bed: {str(e)}', 'danger')
        
        elif action == 'assign_bed':
            try:
                bed_id = request.form.get('bed_id')
                patient_id = request.form.get('patient_id')
                
                bed = Bed.query.get(bed_id)
                if bed.status == 'occupied':
                    flash('Bed is already occupied', 'danger')
                else:
                    bed.status = 'occupied'
                    bed.patient_id = patient_id
                    db.session.commit()
                    flash('Bed assigned successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error assigning bed: {str(e)}', 'danger')
        
        elif action == 'release_bed':
            try:
                bed_id = request.form.get('bed_id')
                bed = Bed.query.get(bed_id)
                bed.status = 'available'
                bed.patient_id = None
                db.session.commit()
                flash('Bed released successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error releasing bed: {str(e)}', 'danger')
        
        return redirect(url_for('manage_beds'))
    
    wards = Ward.query.all()
    beds = Bed.query.order_by(Bed.ward_id, Bed.bed_number).all()
    patients = Patient.query.filter_by(status='active').all()
    
    return render_template('admin/beds.html',
        wards=wards,
        beds=beds,
        patients=patients,
        total_beds=get_total_beds(),
        occupied_beds=get_occupied_beds(),
        available_beds=get_available_beds()
    )

@app.route('/admin/drugs', methods=['GET', 'POST'])
@login_required
def manage_drugs():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                drug = Drug(
                    drug_number=generate_drug_number(),
                    name=request.form.get('name'),
                    specification=request.form.get('specification'),
                    buying_price=float(request.form.get('buying_price')),
                    selling_price=float(request.form.get('selling_price')),
                    stocked_quantity=int(request.form.get('stocked_quantity')),
                    expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()
                )
                db.session.add(drug)
                db.session.commit()
                
                log_audit('create', 'Drug', drug.id, None, {
                    'drug_number': drug.drug_number,
                    'name': drug.name,
                    'specification': drug.specification,
                    'buying_price': drug.buying_price,
                    'selling_price': drug.selling_price,
                    'stocked_quantity': drug.stocked_quantity,
                    'expiry_date': drug.expiry_date
                })
                
                flash('Drug added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding drug: {str(e)}', 'danger')
        
        elif action == 'edit':
            drug_id = request.form.get('drug_id')
            drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
            if drug:
                try:
                    old_values = {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    }
                    
                    drug.name = request.form.get('name')
                    drug.specification = request.form.get('specification')
                    drug.buying_price = float(request.form.get('buying_price'))
                    drug.selling_price = float(request.form.get('selling_price'))
                    drug.stocked_quantity = int(request.form.get('stocked_quantity'))
                    drug.expiry_date = datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()
                    
                    db.session.commit()
                    
                    log_audit('update', 'Drug', drug.id, old_values, {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    })
                    
                    flash('Drug updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating drug: {str(e)}', 'danger')
            else:
                flash('Drug not found', 'danger')
        
        elif action == 'delete':
            drug_id = request.form.get('drug_id')
            drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
            if drug:
                try:
                    log_audit('delete', 'Drug', drug.id, {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    }, None)
                    
                    db.session.delete(drug)
                    db.session.commit()
                    flash('Drug deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting drug: {str(e)}', 'danger')
            else:
                flash('Drug not found', 'danger')
        
        return redirect(url_for('manage_drugs'))
    
    # Handle filter requests
    filter_type = request.args.get('filter', 'all')
    
    # Base query
    query = db.select(Drug)
    
    if filter_type == 'low_stock':
        # Drugs with less than 10 remaining
        query = query.where(Drug.remaining_quantity < 10)
    elif filter_type == 'expiring_soon':
        # Drugs expiring in the next 30 days or already expired
        today = datetime.now().date()
        thirty_days_later = today + timedelta(days=30)
        query = query.where(Drug.expiry_date <= thirty_days_later).order_by(Drug.expiry_date)
    elif filter_type == 'out_of_stock':
        # Drugs with zero or negative remaining quantity
        query = query.where(Drug.remaining_quantity <= 0)
    elif filter_type == 'expired':
        # Only expired drugs
        today = datetime.now().date()
        query = query.where(Drug.expiry_date < today)
    
    # Execute the query
    drugs = db.session.execute(query).scalars().all()
    
    total_value = sum(drug.selling_price * drug.remaining_quantity for drug in drugs)
    return render_template('admin/drugs.html', 
                         drugs=drugs, 
                         total_value=total_value, 
                         current_filter=filter_type,
                         today=datetime.now().date())

@app.route('/admin/drugs/<int:drug_id>')
def get_drug(drug_id):

    drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
    if not drug:
        return jsonify({'error': 'Drug not found'}), 404
    
    return jsonify({
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name,
        'specification': drug.specification,
        'buying_price': drug.buying_price,
        'selling_price': drug.selling_price,
        'stocked_quantity': drug.stocked_quantity,
        'sold_quantity': drug.sold_quantity,
        'expiry_date': drug.expiry_date.strftime('%Y-%m-%d'),
        'remaining_quantity': drug.remaining_quantity,
        'is_expired': drug.expiry_date < datetime.now().date(),
        'expires_soon': drug.expiry_date <= (datetime.now().date() + timedelta(days=30))
    })


@app.route('/admin/controlled-drugs', methods=['GET', 'POST'])
@login_required
def manage_controlled_drugs():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    embed = request.args.get('embed') == '1'

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            try:
                controlled = ControlledDrug(
                    controlled_drug_number=generate_controlled_drug_number(),
                    name=request.form.get('name'),
                    specification=request.form.get('specification'),
                    buying_price=float(request.form.get('buying_price')),
                    selling_price=float(request.form.get('selling_price')),
                    stocked_quantity=int(request.form.get('stocked_quantity')),
                    expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date(),
                )
                db.session.add(controlled)
                db.session.commit()

                log_audit('create', 'ControlledDrug', controlled.id, None, {
                    'controlled_drug_number': controlled.controlled_drug_number,
                    'name': controlled.name,
                    'specification': controlled.specification,
                    'buying_price': float(controlled.buying_price),
                    'selling_price': float(controlled.selling_price),
                    'stocked_quantity': controlled.stocked_quantity,
                    'expiry_date': controlled.expiry_date.isoformat(),
                })

                flash('Controlled drug added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding controlled drug: {str(e)}', 'danger')

        elif action == 'edit':
            controlled_id = request.form.get('controlled_drug_id')
            controlled = db.session.get(ControlledDrug, controlled_id)
            if controlled:
                try:
                    old_values = {
                        'controlled_drug_number': controlled.controlled_drug_number,
                        'name': controlled.name,
                        'specification': controlled.specification,
                        'buying_price': float(controlled.buying_price),
                        'selling_price': float(controlled.selling_price),
                        'stocked_quantity': controlled.stocked_quantity,
                        'sold_quantity': controlled.sold_quantity,
                        'expiry_date': controlled.expiry_date.isoformat(),
                    }

                    controlled.name = request.form.get('name')
                    controlled.specification = request.form.get('specification')
                    controlled.buying_price = float(request.form.get('buying_price'))
                    controlled.selling_price = float(request.form.get('selling_price'))
                    controlled.stocked_quantity = int(request.form.get('stocked_quantity'))
                    controlled.expiry_date = datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()

                    db.session.commit()

                    log_audit('update', 'ControlledDrug', controlled.id, old_values, {
                        'controlled_drug_number': controlled.controlled_drug_number,
                        'name': controlled.name,
                        'specification': controlled.specification,
                        'buying_price': float(controlled.buying_price),
                        'selling_price': float(controlled.selling_price),
                        'stocked_quantity': controlled.stocked_quantity,
                        'sold_quantity': controlled.sold_quantity,
                        'expiry_date': controlled.expiry_date.isoformat(),
                    })

                    flash('Controlled drug updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating controlled drug: {str(e)}', 'danger')
            else:
                flash('Controlled drug not found', 'danger')

        elif action == 'delete':
            controlled_id = request.form.get('controlled_drug_id')
            controlled = db.session.get(ControlledDrug, controlled_id)
            if controlled:
                try:
                    log_audit('delete', 'ControlledDrug', controlled.id, {
                        'controlled_drug_number': controlled.controlled_drug_number,
                        'name': controlled.name,
                        'specification': controlled.specification,
                        'buying_price': float(controlled.buying_price),
                        'selling_price': float(controlled.selling_price),
                        'stocked_quantity': controlled.stocked_quantity,
                        'sold_quantity': controlled.sold_quantity,
                        'expiry_date': controlled.expiry_date.isoformat(),
                    }, None)

                    db.session.delete(controlled)
                    db.session.commit()
                    flash('Controlled drug deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting controlled drug: {str(e)}', 'danger')
            else:
                flash('Controlled drug not found', 'danger')

        return redirect(url_for('manage_controlled_drugs', embed='1' if embed else None))

    filter_type = request.args.get('filter', 'all')
    query = db.select(ControlledDrug)

    if filter_type == 'low_stock':
        query = query.where(ControlledDrug.remaining_quantity < 10)
    elif filter_type == 'expiring_soon':
        today = datetime.now().date()
        thirty_days_later = today + timedelta(days=30)
        query = query.where(ControlledDrug.expiry_date <= thirty_days_later).order_by(ControlledDrug.expiry_date)
    elif filter_type == 'out_of_stock':
        query = query.where(ControlledDrug.remaining_quantity <= 0)
    elif filter_type == 'expired':
        today = datetime.now().date()
        query = query.where(ControlledDrug.expiry_date < today)

    controlled_drugs = db.session.execute(query).scalars().all()
    total_value = sum(float(d.selling_price) * float(d.remaining_quantity) for d in controlled_drugs)

    template_name = 'admin/controlled_drugs_embed.html' if embed else 'admin/controlled_drugs.html'
    return render_template(
        template_name,
        controlled_drugs=controlled_drugs,
        total_value=total_value,
        current_filter=filter_type,
        today=datetime.now().date(),
        expires_soon_cutoff=datetime.now().date() + timedelta(days=30),
    )


@app.route('/admin/controlled-drugs/<int:controlled_drug_id>')
@login_required
def get_controlled_drug(controlled_drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    drug = db.session.get(ControlledDrug, controlled_drug_id)
    if not drug:
        return jsonify({'error': 'Controlled drug not found'}), 404

    return jsonify({
        'id': drug.id,
        'controlled_drug_number': drug.controlled_drug_number,
        'name': drug.name,
        'specification': drug.specification,
        'buying_price': float(drug.buying_price),
        'selling_price': float(drug.selling_price),
        'stocked_quantity': drug.stocked_quantity,
        'sold_quantity': drug.sold_quantity,
        'expiry_date': drug.expiry_date.strftime('%Y-%m-%d'),
        'remaining_quantity': drug.remaining_quantity,
        'is_expired': drug.expiry_date < datetime.now().date(),
        'expires_soon': drug.expiry_date <= (datetime.now().date() + timedelta(days=30)),
    })


@app.route('/api/controlled-drugs/next-number', methods=['GET'])
@login_required
def get_next_controlled_drug_number():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        next_number = generate_controlled_drug_number()
        return jsonify({'controlled_drug_number': next_number}), 200
    except Exception as e:
        app.logger.error(f'Error generating controlled drug number: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/drugs/next-number', methods=['GET'])
@login_required
def get_next_drug_number():
    """Generate the next drug number based on the last added drug"""
    try:
        # Get the last drug by ID (most recently added)
        last_drug = db.session.query(Drug).order_by(Drug.id.desc()).first()
        
        if last_drug:
            # Extract the numeric part from the drug number (e.g., DRG-0001 -> 1)
            drug_num_str = last_drug.drug_number
            if drug_num_str.startswith('DRG-'):
                try:
                    num = int(drug_num_str.replace('DRG-', ''))
                    next_num = num + 1
                except:
                    next_num = 1
            else:
                next_num = 1
        else:
            next_num = 1
        
        # Format the next number as DRG-0001, DRG-0002, etc.
        next_drug_number = f'DRG-{next_num:04d}'
        
        return jsonify({'drug_number': next_drug_number}), 200
    
    except Exception as e:
        app.logger.error(f'Error generating next drug number: {str(e)}')
        return jsonify({'error': str(e)}), 500
    
@app.route('/rs/<int:user_id>', methods=['GET'])
@login_required
def get_user_details(user_id):
    if current_user.role != 'admin':
        return {'error': 'Unauthorized'}, 403
    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'is_active': user.is_active,
        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None
    }
@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                if User.query.filter_by(username=request.form.get('username')).first():
                    flash('Username already exists', 'danger')
                    return redirect(url_for('manage_users'))
                
                if User.query.filter_by(email=request.form.get('email')).first():
                    flash('Email already exists', 'danger')
                    return redirect(url_for('manage_users'))
                
                # Create new user
                user = User(
                    username=request.form.get('username'),
                    email=request.form.get('email'),
                    role=request.form.get('role'),
                    is_active=True if request.form.get('is_active') else False,
                    last_login=None  # Initialize last_login as None for new users
                )
                user.set_password(request.form.get('password'))
                db.session.add(user)
                db.session.commit()
                
                log_audit('create', 'User', user.id, None, {
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active,
                    'last_login': user.last_login
                })
                
                flash('User added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding user: {str(e)}', 'danger')
        
        elif action == 'edit':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                try:
                    old_values = {
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'is_active': user.is_active,
                        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                    }
                    
                    user.username = request.form.get('username')
                    user.email = request.form.get('email')
                    user.role = request.form.get('role')
                    user.is_active = True if request.form.get('is_active') else False
                    
                    if request.form.get('password'):
                        user.set_password(request.form.get('password'))
                    
                    db.session.commit()
                    
                    log_audit('update', 'User', user.id, old_values, {
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'is_active': user.is_active,
                        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                    })
                    
                    flash('User updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating user: {str(e)}', 'danger')
            else:
                flash('User not found', 'danger')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if user.id == current_user.id:
                    flash('You cannot delete your own account', 'danger')
                else:
                    try:
                        log_audit('delete', 'User', user.id, {
                            'username': user.username,
                            'email': user.email,
                            'role': user.role,
                            'is_active': user.is_active,
                            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                        }, None)
                        
                        db.session.delete(user)
                        db.session.commit()
                        flash('User deleted successfully!', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error deleting user: {str(e)}', 'danger')
            else:
                flash('User not found', 'danger')
        
        return redirect(url_for('manage_users'))
    
    # Order users by last login (most recent first) and then by username
    users = User.query.order_by(User.last_login.desc().nullslast(), User.username.asc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/employees', methods=['GET', 'POST'])
@login_required
def manage_employees():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                # Handle empty salary
                salary = request.form.get('salary')
                salary_value = float(salary) if salary and salary.strip() else None
                
                # Handle hire date
                hire_date_str = request.form.get('hire_date')
                hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date() if hire_date_str and hire_date_str.strip() else None
                
                # Handle user_id
                user_id_str = request.form.get('user_id')
                user_id = int(user_id_str) if user_id_str and user_id_str.strip() else None
                
                employee = Employee(
                    name=request.form.get('name'),
                    position=request.form.get('position'),
                    salary=salary_value,
                    hire_date=hire_date,
                    contact=request.form.get('contact'),
                    user_id=user_id
                )
                db.session.add(employee)
                db.session.commit()
                
                log_audit('create', 'Employee', employee.id, None, {
                    'name': employee.name,
                    'position': employee.position,
                    'salary': employee.salary,
                    'hire_date': str(employee.hire_date) if employee.hire_date else None,
                    'contact': employee.contact,
                    'user_id': employee.user_id
                })
                
                flash('Employee added successfully!', 'success')
            except ValueError as e:
                db.session.rollback()
                flash(f'Invalid data format: {str(e)}', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding employee: {str(e)}', 'danger')
        
        elif action == 'edit':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                try:
                    old_values = {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    }
                    
                    # Handle empty salary
                    salary = request.form.get('salary')
                    salary_value = float(salary) if salary and salary.strip() else None
                    
                    # Handle hire date
                    hire_date_str = request.form.get('hire_date')
                    hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date() if hire_date_str and hire_date_str.strip() else None
                    
                    # Handle user_id
                    user_id_str = request.form.get('user_id')
                    user_id = int(user_id_str) if user_id_str and user_id_str.strip() else None
                    
                    employee.name = request.form.get('name')
                    employee.position = request.form.get('position')
                    employee.salary = salary_value
                    employee.hire_date = hire_date
                    employee.contact = request.form.get('contact')
                    employee.user_id = user_id
                    
                    db.session.commit()
                    
                    log_audit('update', 'Employee', employee.id, old_values, {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    })
                    
                    flash('Employee updated successfully!', 'success')
                except ValueError as e:
                    db.session.rollback()
                    flash(f'Invalid data format: {str(e)}', 'danger')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating employee: {str(e)}', 'danger')
            else:
                flash('Employee not found', 'danger')
        
        elif action == 'delete':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                try:
                    log_audit('delete', 'Employee', employee.id, {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    }, None)
                    
                    db.session.delete(employee)
                    db.session.commit()
                    flash('Employee deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting employee: {str(e)}', 'danger')
            else:
                flash('Employee not found', 'danger')
        
        return redirect(url_for('manage_employees'))
    
    employees = Employee.query.all()
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin/employees.html', 
                        employees=employees, 
                        users=users,
                        User=User)

@app.route('/admin/employees/<int:employee_id>')
@login_required
def get_employee(employee_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    employee = db.session.get(Employee, employee_id)  # Fixed: use employee_id parameter
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
        
    return jsonify({
        'id': employee.id,
        'name': employee.name,
        'position': employee.position,
        'salary': employee.salary,
        'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else None,
        'contact': employee.contact,
        'user_id': employee.user_id
    })

@app.route('/admin/reports', methods=['GET', 'POST'])
@login_required
def admin_reports():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    drug_report = None
    service_report = None
    start_date = None
    end_date = None
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        report_type = request.form.get('report_type')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date > end_date:
                flash('Start date cannot be after end date', 'danger')
                return redirect(url_for('admin_reports'))
            
            if report_type == 'drug_sales':
                # Generate drug sales report
                drug_sales = db.session.query(
                    SaleItem.drug_name,
                    func.sum(SaleItem.quantity).label('total_units'),
                    func.sum(SaleItem.total_price).label('total_amount'),
                    func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity).label('total_profit')
                ).join(
                    Drug, SaleItem.drug_id == Drug.id
                ).join(
                    Sale, SaleItem.sale_id == Sale.id
                ).filter(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date + timedelta(days=1),
                    SaleItem.drug_id.isnot(None)
                ).group_by(
                    SaleItem.drug_name
                ).order_by(
                    SaleItem.drug_name
                ).all()
                
                # Calculate totals
                total_sales = sum(sale.total_amount for sale in drug_sales)
                total_profit = sum(sale.total_profit for sale in drug_sales)
                
                drug_report = {
                    'sales': drug_sales,
                    'total_sales': total_sales,
                    'total_profit': total_profit,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
            elif report_type == 'patient_services':
                # Generate patient service report
                service_data = db.session.query(
                    PatientService.service_id,
                    Service.name,
                    func.count(PatientService.id).label('total_services'),
                    func.sum(Service.price).label('total_amount')
                ).join(
                    Service, PatientService.service_id == Service.id
                ).filter(
                    PatientService.created_at >= start_date,
                    PatientService.created_at <= end_date + timedelta(days=1)
                ).group_by(
                    PatientService.service_id,
                    Service.name
                ).order_by(
                    Service.name
                ).all()
                
                # Calculate totals
                total_services = sum(service.total_services for service in service_data)
                total_amount = sum(service.total_amount for service in service_data)
                
                service_report = {
                    'services': service_data,
                    'total_services': total_services,
                    'total_amount': total_amount,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
        except ValueError:
            flash('Invalid date format', 'danger')
    
    return render_template('admin/reports.html',
        drug_report=drug_report,
        service_report=service_report,
        start_date=start_date,
        end_date=end_date
    )

# ==================== REPORTING HELPER FUNCTIONS ====================

def log_report_access(report_type, filters, data_count=0, status='success', error_msg=None):
    """Log report generation for audit trail compliance"""
    try:
        audit_log = ReportAuditLog(
            user_id=current_user.id,
            report_type=report_type,
            filters=filters,
            data_count=data_count,
            ip_address=request.remote_addr,
            status=status,
            error_message=error_msg
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        app.logger.error(f'Failed to log report access: {str(e)}')


def validate_report_data(data_dict):
    """Validate report output for data quality"""
    issues = []
    
    # Check for null values in critical fields
    if data_dict.get('totals'):
        totals = data_dict['totals']
        for key in ['sales_total', 'cogs', 'expenses', 'estimated_profit']:
            if key not in totals or totals[key] is None:
                issues.append(f"Missing or null {key} in totals")
    
    # Verify logical relationships
    if data_dict.get('totals'):
        sales = data_dict['totals'].get('sales_total', 0)
        cogs = data_dict['totals'].get('cogs', 0)
        expenses = data_dict['totals'].get('expenses', 0)
        profit = data_dict['totals'].get('estimated_profit', 0)
        
        # Profit should equal sales - cogs - expenses (with small tolerance for rounding)
        calculated_profit = sales - cogs - expenses
        if abs(profit - calculated_profit) > 1:  # Allow 1 unit rounding error
            issues.append(f"Profit calculation mismatch: expected {calculated_profit}, got {profit}")
        
        # COGS should never exceed sales
        if cogs > sales:
            issues.append(f"COGS ({cogs}) exceeds Sales ({sales})")
    
    return issues


def calculate_trend_metrics(current_data, previous_data):
    """Calculate growth rates and trend indicators"""
    trends = {}
    
    for key in current_data.get('totals', {}):
        current_val = current_data['totals'].get(key, 0)
        previous_val = previous_data['totals'].get(key, 0) if previous_data else 0
        
        if previous_val != 0:
            growth_rate = ((current_val - previous_val) / abs(previous_val)) * 100
            trends[f'{key}_growth'] = round(growth_rate, 2)
            trends[f'{key}_growth_arrow'] = '↑' if growth_rate > 0 else '↓' if growth_rate < 0 else '→'
        else:
            trends[f'{key}_growth'] = None if current_val == 0 else 100
            trends[f'{key}_growth_arrow'] = '→' if current_val == 0 else '↑'
    
    return trends


def format_financial_metrics(totals):
    """Calculate and format additional financial metrics"""
    sales = totals.get('sales_total', 0)
    cogs = totals.get('cogs', 0)
    expenses = totals.get('expenses', 0)
    profit = totals.get('estimated_profit', 0)
    
    metrics = {
        'sales_total': float(sales),
        'cogs': float(cogs),
        'expenses': float(expenses),
        'estimated_profit': float(profit),
        'gross_profit': float(sales - cogs),
        'gross_margin_pct': (((sales - cogs) / sales) * 100) if sales > 0 else 0,
        'operating_margin_pct': ((profit / sales) * 100) if sales > 0 else 0,
        'cogs_pct': ((cogs / sales) * 100) if sales > 0 else 0,
        'expense_pct': ((expenses / sales) * 100) if sales > 0 else 0,
    }
    
    return metrics

# ==================== END REPORTING HELPERS ====================

@app.route('/admin/reports/generate', methods=['GET'])
@login_required
def generate_reports():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get parameters (default to drug_sales if not specified)
    report_type = request.args.get('type', 'drug_sales')
    # Accept legacy report type names from older UI
    if report_type == 'patient_services':
        report_type = 'lab_reports'
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Validate required parameters
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Both start and end dates are required'}), 400
    
    try:
        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        
        if start_date > end_date:
            return jsonify({'error': 'Start date must be before end date'}), 400
    
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    # Reporting granularity
    granularity = request.args.get('granularity', 'daily')  # daily, weekly, monthly, yearly

    # Precompute totals and expenses used across reports
    total_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed'
    ).scalar() or 0

    cogs = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Drug.buying_price), 0)).join(Drug).join(Sale).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed',
        SaleItem.drug_id.isnot(None)
    ).scalar() or 0

    # Profit for drug sales is calculated as: Total Sales Revenue - Cost of Goods Sold (COGS)
    # Expenses are tracked separately and not deducted from drug profit
    estimated_profit = float(total_sales) - float(cogs)

    if report_type == 'drug_sales':
        # Drug sales report logic (legacy simple path)
        drugs = db.session.query(
            Drug.name,
            func.sum(SaleItem.quantity).label('units_sold'),
            func.sum(SaleItem.total_price).label('total_sales'),
            func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity).label('profit')
        ).join(SaleItem).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(Drug.name).all()

        # Build timeseries by day, then bucket according to granularity in Python
        date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('units')
        ).join(SaleItem).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.drug_id.isnot(None)
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        # Convert rows to dict by date
        daily = {}
        for r in date_rows:
            daily[str(r.d)] = {'amount': float(r.amount or 0), 'units': int(r.units or 0)}

        # Helper to bucket dates
        def bucket_dates(daily_dict, gran):
            from datetime import datetime as _dt
            buckets = {}
            for ds, vals in daily_dict.items():
                dt = _dt.strptime(ds, '%Y-%m-%d').date()
                if gran == 'weekly':
                    # ISO week-year key
                    key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
                    label = key
                elif gran == 'monthly':
                    key = f"{dt.year}-{dt.month:02d}"
                    label = key
                elif gran == 'yearly':
                    key = f"{dt.year}"
                    label = key
                else:
                    key = ds
                    label = ds

                if key not in buckets:
                    buckets[key] = {'label': label, 'amount': 0.0, 'units': 0}
                buckets[key]['amount'] += vals['amount']
                buckets[key]['units'] += vals['units']

            # Order buckets by key (for time order keys are sortable strings)
            ordered = [buckets[k] for k in sorted(buckets.keys())]
            labels = [x['label'] for x in ordered]
            amounts = [x['amount'] for x in ordered]
            units = [x['units'] for x in ordered]
            return labels, amounts, units

        labels, amounts, units = bucket_dates(daily, granularity)
        
        # Get Top 10 Most Sold Drugs (Daily, Weekly, Monthly, Yearly) with amounts and percentages
        def get_top_10_drugs(start_dt, end_dt, gran='daily'):
            try:
                top_drugs = db.session.query(
                    Drug.name,
                    func.sum(SaleItem.quantity).label('total_units'),
                    func.sum(SaleItem.total_price).label('total_amount'),
                    func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity).label('profit')
                ).join(SaleItem, Drug.id == SaleItem.drug_id).join(Sale, SaleItem.sale_id == Sale.id).filter(
                    Sale.created_at >= start_dt,
                    Sale.created_at <= end_dt,
                    Sale.status == 'completed',
                    SaleItem.drug_id.isnot(None)
                ).group_by(Drug.name).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all()
                
                # Calculate total for percentage calculations
                total_units = sum(int(d.total_units or 0) for d in top_drugs)
                total_amount = sum(float(d.total_amount or 0) for d in top_drugs)
                total_profit = sum(float(d.profit or 0) for d in top_drugs)
                
                return {
                    'labels': [d.name[:20] for d in top_drugs],
                    'units': [int(d.total_units or 0) for d in top_drugs],
                    'amounts': [float(d.total_amount or 0) for d in top_drugs],
                    'profits': [float(d.profit or 0) for d in top_drugs],
                    'percentages': [round((int(d.total_units or 0) / total_units * 100) if total_units > 0 else 0, 2) for d in top_drugs],
                    'total_units': total_units,
                    'total_amount': total_amount,
                    'total_profit': total_profit
                }
            except Exception as e:
                app.logger.error(f"Error getting top 10 drugs: {str(e)}")
                return {
                    'labels': [],
                    'units': [],
                    'amounts': [],
                    'profits': [],
                    'percentages': [],
                    'total_units': 0,
                    'total_amount': 0,
                    'total_profit': 0
                }

        # Calculate top 10 for different granularities including yearly
        if granularity == 'daily':
            top10_daily = get_top_10_drugs(start_date, end_date, 'daily')
            top10_weekly = get_top_10_drugs(start_date - timedelta(days=7), end_date, 'weekly')
            top10_monthly = get_top_10_drugs(start_date - timedelta(days=30), end_date, 'monthly')
            top10_yearly = get_top_10_drugs(start_date - timedelta(days=365), end_date, 'yearly')
        elif granularity == 'weekly':
            top10_daily = get_top_10_drugs(start_date, end_date, 'daily')
            top10_weekly = get_top_10_drugs(start_date - timedelta(days=14), end_date, 'weekly')
            top10_monthly = get_top_10_drugs(start_date - timedelta(days=60), end_date, 'monthly')
            top10_yearly = get_top_10_drugs(start_date - timedelta(days=365), end_date, 'yearly')
        elif granularity == 'monthly':
            top10_daily = get_top_10_drugs(start_date - timedelta(days=1), end_date, 'daily')
            top10_weekly = get_top_10_drugs(start_date - timedelta(days=7), end_date, 'weekly')
            top10_monthly = get_top_10_drugs(start_date - timedelta(days=90), end_date, 'monthly')
            top10_yearly = get_top_10_drugs(start_date - timedelta(days=365), end_date, 'yearly')
        else:  # yearly
            top10_daily = get_top_10_drugs(start_date - timedelta(days=1), end_date, 'daily')
            top10_weekly = get_top_10_drugs(start_date - timedelta(days=7), end_date, 'weekly')
            top10_monthly = get_top_10_drugs(start_date - timedelta(days=30), end_date, 'monthly')
            top10_yearly = get_top_10_drugs(start_date - timedelta(days=365), end_date, 'yearly')

        # Get Patient vs Over-the-Counter Sales
        # Patient sales: transactions linked to IP or OP patient numbers
        patient_sales_data = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0).label('patient_amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('patient_units')
        ).join(SaleItem, Sale.id == SaleItem.sale_id).outerjoin(Patient, Sale.patient_id == Patient.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.drug_id.isnot(None),
            ((Patient.ip_number.isnot(None)) | (Patient.op_number.isnot(None)))
        ).first()

        # Over-the-counter: transactions without patient link (walking customers)
        overcounter_sales_data = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0).label('overcounter_amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('overcounter_units')
        ).join(SaleItem, Sale.id == SaleItem.sale_id).outerjoin(Patient, Sale.patient_id == Patient.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.drug_id.isnot(None),
            Sale.patient_id.is_(None)
        ).first()

        patient_amount = float(patient_sales_data.patient_amount or 0) if patient_sales_data else 0
        patient_units = int(patient_sales_data.patient_units or 0) if patient_sales_data else 0
        overcounter_amount = float(overcounter_sales_data.overcounter_amount or 0) if overcounter_sales_data else 0
        overcounter_units = int(overcounter_sales_data.overcounter_units or 0) if overcounter_sales_data else 0
        
        # Build response
        totals = {
            'sales_total': float(total_sales),
            'cogs': float(cogs),
            'estimated_profit': float(estimated_profit)
        }
        
        response_data = {
            'status': 'success',
            'report_type': 'drug_sales',
            'granularity': granularity,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': [{
                'name': d.name,
                'units_sold': int(d.units_sold or 0),
                'total_sales': float(d.total_sales or 0),
                'profit': float(d.profit or 0)
            } for d in drugs],
            'charts': {
                'labels': labels,
                'amounts': amounts,
                'units': units,
                'totals': totals,
                'top10_daily': top10_daily,
                'top10_weekly': top10_weekly,
                'top10_monthly': top10_monthly,
                'top10_yearly': top10_yearly,
                'patient_sales': patient_amount,
                'patient_units': patient_units,
                'patient_percentage': round((patient_amount / total_sales * 100) if total_sales > 0 else 0, 2),
                'overcounter_sales': overcounter_amount,
                'overcounter_units': overcounter_units,
                'overcounter_percentage': round((overcounter_amount / total_sales * 100) if total_sales > 0 else 0, 2)
            },
            'metrics': format_financial_metrics(totals)
        }
        
        # Validate data quality
        issues = validate_report_data(response_data)
        if issues:
            response_data['data_quality_issues'] = issues
        
        # Log report access for audit trail
        log_report_access(
            report_type='drug_sales',
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'granularity': granularity},
            data_count=len(drugs),
            status='success'
        )

        return jsonify(response_data)

    def bucket_dates(daily_dict, gran):
        buckets = {}
        for ds, vals in daily_dict.items():
            dt = datetime.strptime(ds, '%Y-%m-%d').date()
            if gran == 'weekly':
                key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
                label = key
            elif gran == 'monthly':
                key = f"{dt.year}-{dt.month:02d}"
                label = key
            elif gran == 'yearly':
                key = f"{dt.year}"
                label = key
            else:
                key = ds
                label = ds

            if key not in buckets:
                buckets[key] = {'label': label, 'amount': 0.0, 'units': 0}
            buckets[key]['amount'] += float(vals.get('amount', 0) or 0)
            buckets[key]['units'] += int(vals.get('units', vals.get('count', 0)) or 0)

        ordered = [buckets[k] for k in sorted(buckets.keys())]
        labels = [x['label'] for x in ordered]
        amounts = [x['amount'] for x in ordered]
        units = [x['units'] for x in ordered]
        return labels, amounts, units

    # ==================== LAB REPORTS (Monetary, by patient) ====================
    if report_type == 'lab_reports':
        # Overall lab revenue and count
        lab_total_revenue = db.session.query(func.coalesce(func.sum(SaleItem.total_price), 0)).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).scalar() or 0

        lab_total_count = db.session.query(func.coalesce(func.count(SaleItem.id), 0)).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).scalar() or 0

        # Group by patient and test
        lab_rows = db.session.query(
            Patient.id.label('patient_id'),
            Patient.name.label('patient_name'),
            LabTest.id.label('test_id'),
            LabTest.name.label('test_name'),
            func.count(SaleItem.id).label('count'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount')
        ).join(Sale, Sale.patient_id == Patient.id).join(SaleItem, SaleItem.sale_id == Sale.id).join(LabTest, SaleItem.lab_test_id == LabTest.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).group_by(Patient.id, Patient.name, LabTest.id, LabTest.name).order_by(Patient.name, LabTest.name).all()

        patients_by_id = {}
        for r in lab_rows:
            pid = int(r.patient_id)
            if pid not in patients_by_id:
                patients_by_id[pid] = {
                    'patient_id': pid,
                    'patient_name': r.patient_name,
                    'tests': [],
                    'total_count': 0,
                    'total_revenue': 0.0
                }
            count = int(r.count or 0)
            amount = float(r.amount or 0)
            patients_by_id[pid]['tests'].append({
                'test_id': int(r.test_id),
                'test_name': r.test_name,
                'count': count,
                'amount': amount
            })
            patients_by_id[pid]['total_count'] += count
            patients_by_id[pid]['total_revenue'] += amount

        patient_rows = sorted(patients_by_id.values(), key=lambda x: (x['patient_name'] or ''))

        # Time series for lab revenue
        lab_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.count(SaleItem.id), 0).label('count')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.lab_test_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        lab_daily = {str(r.d): {'amount': float(r.amount or 0), 'count': int(r.count or 0)} for r in lab_date_rows}
        labels, amounts, counts = bucket_dates(lab_daily, granularity)

        # Breakdown by test (for pie + bar)
        test_breakdown_rows = db.session.query(
            LabTest.name.label('test_name'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.count(SaleItem.id), 0).label('count')
        ).join(SaleItem, SaleItem.lab_test_id == LabTest.id).join(Sale, SaleItem.sale_id == Sale.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).group_by(LabTest.name).order_by(func.sum(SaleItem.total_price).desc()).all()

        top_tests = {
            'labels': [r.test_name[:24] for r in test_breakdown_rows[:10]],
            'amounts': [float(r.amount or 0) for r in test_breakdown_rows[:10]],
            'counts': [int(r.count or 0) for r in test_breakdown_rows[:10]]
        }

        # Top patients by lab spend
        top_patient_rows = db.session.query(
            Patient.name.label('patient_name'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount')
        ).join(Sale, Sale.patient_id == Patient.id).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).group_by(Patient.name).order_by(func.sum(SaleItem.total_price).desc()).limit(10).all()

        top_patients = {
            'labels': [r.patient_name[:24] if r.patient_name else 'Unknown' for r in top_patient_rows],
            'amounts': [float(r.amount or 0) for r in top_patient_rows]
        }

        totals = {
            'lab_revenue': float(lab_total_revenue),
            'lab_count': int(lab_total_count)
        }

        response_data = {
            'status': 'success',
            'report_type': 'lab_reports',
            'granularity': granularity,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': patient_rows,
            'charts': {
                'labels': labels,
                'amounts': amounts,
                'units': counts,
                'totals': totals,
                'lab_breakdown': {
                    'labels': [r.test_name[:24] for r in test_breakdown_rows],
                    'amounts': [float(r.amount or 0) for r in test_breakdown_rows]
                },
                'top_tests': top_tests,
                'top_patients': top_patients
            }
        }

        log_report_access(
            report_type='lab_reports',
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'granularity': granularity},
            data_count=len(patient_rows),
            status='success'
        )

        return jsonify(response_data)

    # ==================== GENERAL REPORT (Drugs + Labs) ====================
    if report_type == 'general':
        drug_revenue = db.session.query(func.coalesce(func.sum(SaleItem.total_price), 0)).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.drug_id.isnot(None)
        ).scalar() or 0

        lab_revenue = db.session.query(func.coalesce(func.sum(SaleItem.total_price), 0)).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).scalar() or 0

        total_revenue = float(drug_revenue) + float(lab_revenue)

        drug_profit = db.session.query(func.coalesce(func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity), 0)).join(Drug).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.drug_id.isnot(None)
        ).scalar() or 0

        # Time series for both streams
        drug_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('units')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.drug_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        lab_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.count(SaleItem.id), 0).label('count')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.lab_test_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        drug_daily = {str(r.d): {'amount': float(r.amount or 0), 'units': int(r.units or 0)} for r in drug_date_rows}
        lab_daily = {str(r.d): {'amount': float(r.amount or 0), 'count': int(r.count or 0)} for r in lab_date_rows}

        labels_drug, drug_amounts, drug_units = bucket_dates(drug_daily, granularity)
        labels_lab, lab_amounts, lab_counts = bucket_dates(lab_daily, granularity)
        labels = labels_drug if len(labels_drug) >= len(labels_lab) else labels_lab

        # Top drugs by revenue
        top_drugs = db.session.query(
            Drug.name.label('name'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('units'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity), 0).label('profit')
        ).join(SaleItem).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(Drug.name).order_by(func.sum(SaleItem.total_price).desc()).limit(10).all()

        top_labs = db.session.query(
            LabTest.name.label('name'),
            func.coalesce(func.count(SaleItem.id), 0).label('count'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount')
        ).join(SaleItem, SaleItem.lab_test_id == LabTest.id).join(Sale, SaleItem.sale_id == Sale.id).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed',
            SaleItem.lab_test_id.isnot(None)
        ).group_by(LabTest.name).order_by(func.sum(SaleItem.total_price).desc()).limit(10).all()

        combined_items = []
        for d in top_drugs:
            combined_items.append({
                'category': 'Drug',
                'name': d.name,
                'units': int(d.units or 0),
                'total_revenue': float(d.amount or 0),
                'profit': float(d.profit or 0)
            })
        for t in top_labs:
            combined_items.append({
                'category': 'Lab',
                'name': t.name,
                'units': int(t.count or 0),
                'total_revenue': float(t.amount or 0)
            })

        totals = {
            'total_revenue': float(total_revenue),
            'drug_revenue': float(drug_revenue),
            'lab_revenue': float(lab_revenue),
            'drug_cogs': float(cogs),
            'drug_profit': float(drug_profit)
        }

        response_data = {
            'status': 'success',
            'report_type': 'general',
            'granularity': granularity,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': sorted(combined_items, key=lambda x: x.get('total_revenue', 0), reverse=True),
            'charts': {
                'labels': labels,
                'drug_amounts': drug_amounts,
                'lab_amounts': lab_amounts,
                'drug_units': drug_units,
                'lab_counts': lab_counts,
                'totals': totals,
                'top_drugs': {
                    'labels': [d.name[:24] for d in top_drugs],
                    'amounts': [float(d.amount or 0) for d in top_drugs]
                },
                'top_tests': {
                    'labels': [t.name[:24] for t in top_labs],
                    'amounts': [float(t.amount or 0) for t in top_labs]
                }
            }
        }

        log_report_access(
            report_type='general',
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'granularity': granularity},
            data_count=len(combined_items),
            status='success'
        )

        return jsonify(response_data)
    
    # Additional advanced reporting options
    # Additional advanced reporting options
    subtype = request.args.get('subtype')  # e.g., 'lab' or 'drugs' for patient reports
    patient_kind = request.args.get('patient_kind')  # 'inpatient' | 'outpatient' | None
    granularity = request.args.get('granularity', 'daily')  # daily, weekly, monthly, yearly

    # Normalize end_date to include entire day already done above via + timedelta

    # Compute high-level totals
    total_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed'
    ).scalar() or 0

    cogs = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Drug.buying_price), 0)).join(Drug).join(Sale).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed',
        SaleItem.drug_id.isnot(None)
    ).scalar() or 0

    expenses_list = db.session.query(Expense).filter(
        Expense.created_at >= start_date,
        Expense.created_at <= end_date
    ).all()

    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.created_at >= start_date,
        Expense.created_at <= end_date
    ).scalar() or 0

    estimated_profit = float(total_sales) - float(cogs) - float(total_expenses)

    # Patients report: inpatients/outpatients, subtype lab/drugs
    if report_type == 'patients':
        patient_filter = []
        if patient_kind == 'inpatient':
            patient_filter.append(Patient.date_of_admission.isnot(None))
        elif patient_kind == 'outpatient':
            patient_filter.append(Patient.op_number.isnot(None))

        results = []

        # LABS: combine clinical lab counts (PatientLab) and financial lab sales (SaleItem.lab_test_id)
        if subtype in (None, 'lab'):
            lab_rows = db.session.query(
                Patient.id.label('patient_id'),
                Patient.name.label('patient_name'),
                func.coalesce(func.count(PatientLab.id), 0).label('lab_tests_count'),
                func.coalesce(func.sum(SaleItem.total_price), 0).label('lab_sales_amount')
            ).select_from(Patient).outerjoin(Sale, Sale.patient_id == Patient.id).outerjoin(SaleItem, db.and_(SaleItem.sale_id == Sale.id, SaleItem.lab_test_id.isnot(None))).outerjoin(PatientLab, PatientLab.patient_id == Patient.id).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed'
            )

            if patient_filter:
                lab_rows = lab_rows.filter(*patient_filter)

            lab_rows = lab_rows.group_by(Patient.id).order_by(Patient.name).all()

            for r in lab_rows:
                results.append({
                    'patient_id': r.patient_id,
                    'patient_name': r.patient_name,
                    'lab_tests_count': int(r.lab_tests_count or 0),
                    'lab_sales_amount': float(r.lab_sales_amount or 0)
                })

        # DRUGS: drugs sold to patients (from SaleItem)
        if subtype in (None, 'drugs'):
            drug_rows = db.session.query(
                Patient.id.label('patient_id'),
                Patient.name.label('patient_name'),
                func.coalesce(func.sum(SaleItem.quantity), 0).label('units'),
                func.coalesce(func.sum(SaleItem.total_price), 0).label('amount')
            ).join(Sale, Sale.patient_id == Patient.id).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed',
                SaleItem.drug_id.isnot(None)
            )

            if patient_filter:
                drug_rows = drug_rows.filter(*patient_filter)

            drug_rows = drug_rows.group_by(Patient.id).order_by(Patient.name).all()

            # Merge into results keyed by patient
            results_by_id = {r['patient_id']: r for r in results}
            for r in drug_rows:
                pid = r.patient_id
                if pid in results_by_id:
                    results_by_id[pid].update({
                        'drug_units': int(r.units or 0),
                        'drug_amount': float(r.amount or 0)
                    })
                else:
                    results.append({
                        'patient_id': r.patient_id,
                        'patient_name': r.patient_name,
                        'drug_units': int(r.units or 0),
                        'drug_amount': float(r.amount or 0)
                    })

        # Build time series for patient-related lab and drug sales
        # LAB timeseries
        lab_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.count(SaleItem.id), 0).label('count')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.lab_test_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        # DRUG timeseries
        drug_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('units')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.drug_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        # Convert rows to daily dict
        lab_daily = {str(r.d): {'amount': float(r.amount or 0), 'count': int(r.count or 0)} for r in lab_date_rows}
        drug_daily = {str(r.d): {'amount': float(r.amount or 0), 'units': int(r.units or 0)} for r in drug_date_rows}

        # Reuse bucketing logic for granularity
        def bucket_dates(daily_dict, gran):
            buckets = {}
            for ds, vals in daily_dict.items():
                dt = datetime.strptime(ds, '%Y-%m-%d').date()
                if gran == 'weekly':
                    key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
                    label = key
                elif gran == 'monthly':
                    key = f"{dt.year}-{dt.month:02d}"
                    label = key
                elif gran == 'yearly':
                    key = f"{dt.year}"
                    label = key
                else:
                    key = ds
                    label = ds

                if key not in buckets:
                    buckets[key] = {'label': label, 'amount': 0.0, 'units': 0}
                buckets[key]['amount'] += vals.get('amount', 0)
                # some buckets have 'count' other have 'units'
                buckets[key]['units'] += vals.get('units', vals.get('count', 0))

            ordered = [buckets[k] for k in sorted(buckets.keys())]
            labels = [x['label'] for x in ordered]
            amounts = [x['amount'] for x in ordered]
            units = [x['units'] for x in ordered]
            return labels, amounts, units

        lab_labels, lab_amounts, lab_counts = bucket_dates(lab_daily, granularity)
        drug_labels, drug_amounts, drug_units = bucket_dates(drug_daily, granularity)

        # Build response
        totals = {
            'sales_total': float(total_sales),
            'cogs': float(cogs),
            'expenses': float(total_expenses),
            'estimated_profit': float(estimated_profit)
        }
        
        response_data = {
            'status': 'success',
            'report_type': 'patients',
            'subtype': subtype,
            'patient_kind': patient_kind or 'all',
            'granularity': granularity,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': results,
            'totals': totals,
            'expenses': [{
                'expense_number': e.expense_number,
                'expense_type': e.expense_type,
                'amount': float(e.amount),
                'description': e.description,
                'created_at': e.created_at.strftime('%Y-%m-%d') if e.created_at else None
            } for e in expenses_list],
            'charts': {
                'labels': lab_labels if len(lab_labels) >= len(drug_labels) else drug_labels,
                'lab_amounts': lab_amounts,
                'lab_counts': lab_counts,
                'drug_amounts': drug_amounts,
                'drug_units': drug_units,
                'totals': totals
            },
            'metrics': format_financial_metrics(totals)
        }
        
        # Validate data quality
        issues = validate_report_data(response_data)
        if issues:
            response_data['data_quality_issues'] = issues
        
        # Log report access for audit trail
        log_report_access(
            report_type='patients',
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'granularity': granularity, 'subtype': subtype, 'patient_kind': patient_kind},
            data_count=len(results),
            status='success'
        )

        return jsonify(response_data)
    
    # Additional advanced reporting options
    subtype = request.args.get('subtype')  # e.g., 'lab' or 'drugs' for patient reports
    patient_kind = request.args.get('patient_kind')  # 'inpatient' | 'outpatient' | None
    granularity = request.args.get('granularity', 'daily')  # daily, weekly, monthly, yearly

    # Normalize end_date to include entire day already done above via + timedelta

    # Compute high-level totals
    total_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed'
    ).scalar() or 0

    cogs = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Drug.buying_price), 0)).join(Drug).join(Sale).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == 'completed',
        SaleItem.drug_id.isnot(None)
    ).scalar() or 0

    expenses_list = db.session.query(Expense).filter(
        Expense.created_at >= start_date,
        Expense.created_at <= end_date
    ).all()

    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.created_at >= start_date,
        Expense.created_at <= end_date
    ).scalar() or 0

    estimated_profit = float(total_sales) - float(cogs) - float(total_expenses)

    # Patients report: inpatients/outpatients, subtype lab/drugs
    if report_type == 'patients':
        patient_filter = []
        if patient_kind == 'inpatient':
            patient_filter.append(Patient.date_of_admission.isnot(None))
        elif patient_kind == 'outpatient':
            patient_filter.append(Patient.op_number.isnot(None))

        results = []

        # LABS: combine clinical lab counts (PatientLab) and financial lab sales (SaleItem.lab_test_id)
        if subtype in (None, 'lab'):
            lab_rows = db.session.query(
                Patient.id.label('patient_id'),
                Patient.name.label('patient_name'),
                func.coalesce(func.count(PatientLab.id), 0).label('lab_tests_count'),
                func.coalesce(func.sum(SaleItem.total_price), 0).label('lab_sales_amount')
            ).select_from(Patient).outerjoin(Sale, Sale.patient_id == Patient.id).outerjoin(SaleItem, db.and_(SaleItem.sale_id == Sale.id, SaleItem.lab_test_id.isnot(None))).outerjoin(PatientLab, PatientLab.patient_id == Patient.id).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed'
            )

            if patient_filter:
                lab_rows = lab_rows.filter(*patient_filter)

            lab_rows = lab_rows.group_by(Patient.id).order_by(Patient.name).all()

            for r in lab_rows:
                results.append({
                    'patient_id': r.patient_id,
                    'patient_name': r.patient_name,
                    'lab_tests_count': int(r.lab_tests_count or 0),
                    'lab_sales_amount': float(r.lab_sales_amount or 0)
                })

        # DRUGS: drugs sold to patients (from SaleItem)
        if subtype in (None, 'drugs'):
            drug_rows = db.session.query(
                Patient.id.label('patient_id'),
                Patient.name.label('patient_name'),
                func.coalesce(func.sum(SaleItem.quantity), 0).label('units'),
                func.coalesce(func.sum(SaleItem.total_price), 0).label('amount')
            ).join(Sale, Sale.patient_id == Patient.id).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed',
                SaleItem.drug_id.isnot(None)
            )

            if patient_filter:
                drug_rows = drug_rows.filter(*patient_filter)

            drug_rows = drug_rows.group_by(Patient.id).order_by(Patient.name).all()

            # Merge into results keyed by patient
            results_by_id = {r['patient_id']: r for r in results}
            for r in drug_rows:
                pid = r.patient_id
                if pid in results_by_id:
                    results_by_id[pid].update({
                        'drug_units': int(r.units or 0),
                        'drug_amount': float(r.amount or 0)
                    })
                else:
                    results.append({
                        'patient_id': r.patient_id,
                        'patient_name': r.patient_name,
                        'drug_units': int(r.units or 0),
                        'drug_amount': float(r.amount or 0)
                    })

        # Build time series for patient-related lab and drug sales
        # LAB timeseries
        lab_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.count(SaleItem.id), 0).label('count')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.lab_test_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        # DRUG timeseries
        drug_date_rows = db.session.query(
            func.date(Sale.created_at).label('d'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('amount'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('units')
        ).join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            SaleItem.drug_id.isnot(None),
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

        # Convert rows to daily dict
        lab_daily = {str(r.d): {'amount': float(r.amount or 0), 'count': int(r.count or 0)} for r in lab_date_rows}
        drug_daily = {str(r.d): {'amount': float(r.amount or 0), 'units': int(r.units or 0)} for r in drug_date_rows}

        # Reuse bucketing logic for granularity
        def bucket_dates(daily_dict, gran):
            buckets = {}
            for ds, vals in daily_dict.items():
                dt = datetime.strptime(ds, '%Y-%m-%d').date()
                if gran == 'weekly':
                    key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
                    label = key
                elif gran == 'monthly':
                    key = f"{dt.year}-{dt.month:02d}"
                    label = key
                elif gran == 'yearly':
                    key = f"{dt.year}"
                    label = key
                else:
                    key = ds
                    label = ds

                if key not in buckets:
                    buckets[key] = {'label': label, 'amount': 0.0, 'units': 0}
                buckets[key]['amount'] += vals.get('amount', 0)
                # some buckets have 'count' other have 'units'
                buckets[key]['units'] += vals.get('units', vals.get('count', 0))

            ordered = [buckets[k] for k in sorted(buckets.keys())]
            labels = [x['label'] for x in ordered]
            amounts = [x['amount'] for x in ordered]
            units = [x['units'] for x in ordered]
            return labels, amounts, units

        lab_labels, lab_amounts, lab_counts = bucket_dates(lab_daily, granularity)
        drug_labels, drug_amounts, drug_units = bucket_dates(drug_daily, granularity)

        # Build response
        totals = {
            'sales_total': float(total_sales),
            'cogs': float(cogs),
            'expenses': float(total_expenses),
            'estimated_profit': float(estimated_profit)
        }
        
        response_data = {
            'status': 'success',
            'report_type': 'patients',
            'subtype': subtype,
            'patient_kind': patient_kind or 'all',
            'granularity': granularity,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': results,
            'totals': totals,
            'expenses': [{
                'expense_number': e.expense_number,
                'expense_type': e.expense_type,
                'amount': float(e.amount),
                'description': e.description,
                'created_at': e.created_at.strftime('%Y-%m-%d') if e.created_at else None
            } for e in expenses_list],
            'charts': {
                'labels': lab_labels if len(lab_labels) >= len(drug_labels) else drug_labels,
                'lab_amounts': lab_amounts,
                'lab_counts': lab_counts,
                'drug_amounts': drug_amounts,
                'drug_units': drug_units,
                'totals': totals
            },
            'metrics': format_financial_metrics(totals)
        }
        
        # Validate data quality
        issues = validate_report_data(response_data)
        if issues:
            response_data['data_quality_issues'] = issues
        
        # Log report access for audit trail
        log_report_access(
            report_type='patients',
            filters={'start_date': start_date_str, 'end_date': end_date_str, 'granularity': granularity, 'subtype': subtype, 'patient_kind': patient_kind},
            data_count=len(results),
            status='success'
        )

        return jsonify(response_data)
def quality_metrics_report():
    """Clinical quality metrics dashboard (readmission, mortality, outcomes)"""
    if current_user.role not in ['admin', 'clinical_director']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Both start and end dates are required'}), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        
        # Get quality metrics for the period
        quality_data = db.session.query(QualityMetric).filter(
            QualityMetric.admission_date >= start_date,
            QualityMetric.admission_date <= end_date
        ).all()
        
        # Calculate aggregated metrics
        total_admissions = len(quality_data)
        readmissions = len([q for q in quality_data if q.readmitted_within_30d])
        deaths = len([q for q in quality_data if q.discharge_status == 'died'])
        average_los = sum([q.length_of_stay for q in quality_data if q.length_of_stay]) / len([q for q in quality_data if q.length_of_stay]) if any(q.length_of_stay for q in quality_data) else 0
        infections = len([q for q in quality_data if q.infections_acquired])
        adverse_events_total = sum([q.adverse_events for q in quality_data])
        
        response = {
            'status': 'success',
            'report_type': 'quality_metrics',
            'start_date': start_date_str,
            'end_date': end_date_str,
            'metrics': {
                'total_admissions': total_admissions,
                'readmissions': readmissions,
                'readmission_rate_pct': (readmissions / total_admissions * 100) if total_admissions > 0 else 0,
                'deaths': deaths,
                'mortality_rate_pct': (deaths / total_admissions * 100) if total_admissions > 0 else 0,
                'average_los_days': round(average_los, 1),
                'hospital_acquired_infections': infections,
                'infection_rate_pct': (infections / total_admissions * 100) if total_admissions > 0 else 0,
                'total_adverse_events': adverse_events_total,
                'adverse_event_rate_pct': (adverse_events_total / total_admissions * 100) if total_admissions > 0 else 0
            },
            'data': [{
                'patient_id': q.patient_id,
                'admission_date': q.admission_date.isoformat(),
                'discharge_status': q.discharge_status,
                'los_days': q.length_of_stay,
                'readmitted': q.readmitted_within_30d,
                'diagnosis': q.primary_diagnosis,
                'adverse_events': q.adverse_events,
                'infection': q.infections_acquired
            } for q in quality_data]
        }
        
        # Log access
        log_report_access(
            report_type='quality_metrics',
            filters={'start_date': start_date_str, 'end_date': end_date_str},
            data_count=len(quality_data),
            status='success'
        )
        
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f'Quality metrics report error: {str(e)}', exc_info=True)
        log_report_access(
            report_type='quality_metrics',
            filters={},
            status='error',
            error_msg=str(e)
        )
        return jsonify({'error': 'Failed to generate quality metrics report', 'message': str(e)}), 500


@app.route('/admin/reports/provider-performance', methods=['GET'])
@login_required
def provider_performance_report():
    """Provider (doctor) performance metrics"""
    if current_user.role not in ['admin', 'clinical_director']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Both start and end dates are required'}), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        
        # Get providers and their metrics
        providers = db.session.query(User).filter(User.role.in_(['doctor', 'provider'])).all()
        
        provider_data = []
        for provider in providers:
            # Count patients seen (from sales)
            sales = db.session.query(Sale).filter(
                Sale.user_id == provider.id,
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed'
            ).all()
            
            patients_count = len(set([s.patient_id for s in sales if s.patient_id]))
            total_revenue = sum([s.total_amount for s in sales])
            avg_patient_value = (total_revenue / patients_count) if patients_count > 0 else 0
            
            # Get quality metrics for this provider
            provider_quality = db.session.query(QualityMetric).filter(
                QualityMetric.admission_date >= start_date,
                QualityMetric.admission_date <= end_date
            ).all()
            
            readmissions = len([q for q in provider_quality if q.readmitted_within_30d])
            
            provider_data.append({
                'provider_id': provider.id,
                'provider_name': provider.username,
                'full_name': f"{provider.first_name} {provider.last_name}",
                'patients_seen': patients_count,
                'total_revenue': float(total_revenue),
                'average_patient_value': float(avg_patient_value),
                'readmissions': readmissions,
                'transactions': len(sales)
            })
        
        response = {
            'status': 'success',
            'report_type': 'provider_performance',
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': provider_data
        }
        
        # Log access
        log_report_access(
            report_type='provider_performance',
            filters={'start_date': start_date_str, 'end_date': end_date_str},
            data_count=len(provider_data),
            status='success'
        )
        
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f'Provider performance report error: {str(e)}', exc_info=True)
        log_report_access(
            report_type='provider_performance',
            filters={},
            status='error',
            error_msg=str(e)
        )
        return jsonify({'error': 'Failed to generate provider performance report', 'message': str(e)}), 500


@app.route('/admin/reports/budget-variance', methods=['GET'])
@login_required
def budget_variance_report():
    """Budget vs. actual variance analysis"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        fiscal_year = request.args.get('fiscal_year', str(datetime.now().year), type=str)
        
        # Get all department budgets for this year
        budgets = db.session.query(DepartmentBudget).filter(
            DepartmentBudget.fiscal_year == int(fiscal_year)
        ).all()
        
        budget_data = []
        for budget in budgets:
            variance_pct = (budget.variance / budget.budgeted_amount * 100) if budget.budgeted_amount > 0 else 0
            
            budget_data.append({
                'department': budget.department_name,
                'budgeted': float(budget.budgeted_amount),
                'actual': float(budget.actual_amount),
                'variance': float(budget.variance),
                'variance_pct': round(variance_pct, 2),
                'status': 'under' if budget.variance < 0 else 'over',
                'notes': budget.notes
            })
        
        total_budgeted = sum([b.budgeted_amount for b in budgets])
        total_actual = sum([b.actual_amount for b in budgets])
        total_variance = total_actual - total_budgeted
        
        response = {
            'status': 'success',
            'report_type': 'budget_variance',
            'fiscal_year': fiscal_year,
            'totals': {
                'budgeted': float(total_budgeted),
                'actual': float(total_actual),
                'variance': float(total_variance),
                'variance_pct': round((total_variance / total_budgeted * 100) if total_budgeted > 0 else 0, 2)
            },
            'data': budget_data
        }
        
        # Log access
        log_report_access(
            report_type='budget_variance',
            filters={'fiscal_year': fiscal_year},
            data_count=len(budget_data),
            status='success'
        )
        
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f'Budget variance report error: {str(e)}', exc_info=True)
        log_report_access(
            report_type='budget_variance',
            filters={},
            status='error',
            error_msg=str(e)
        )
        return jsonify({'error': 'Failed to generate budget variance report', 'message': str(e)}), 500


# ==================== END ENHANCED REPORTING ENDPOINTS ====================

@app.route('/admin/transactions')
@login_required
def manage_transactions():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('admin/transactions.html', transactions=transactions)

# Configuration for backup
BACKUP_CONFIG = {
    'local_storage_path': os.path.join(app.instance_path, 'backups'),
    's3_bucket': os.getenv('AWS_BACKUP_BUCKET', 'your-backup-bucket'),
    'encryption_key': os.getenv('BACKUP_ENCRYPTION_KEY'),
    'tables_to_backup': [
        'appointments', 'audit_logs', 'beds', 'debt_payments', 
        'debtors', 'drug', 'drug_dosage', 'employees', 'expenses', 
        'patients', 'patient_services', 'payroll', 'purchase_items', 'purchases', 'sales', 
        'service_items', 'services', 'transactions', 'user', 'wards'
    ]
}
if not BACKUP_CONFIG['encryption_key']:
    raise RuntimeError("Missing BACKUP_ENCRYPTION_KEY")

# Initialize S3 client if configured
if os.getenv('AWS_ACCESS_KEY_ID'):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
else:
    s3_client = None

@app.route('/admin/backup', methods=['GET', 'POST'])
@login_required
def backup_management():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_backup':
            try:
                # Create a new backup record
                backup = BackupRecord(
                    backup_type='manual',
                    user_id=current_user.id,
                    notes=request.form.get('notes', ''),
                    status='in_progress'
                )
                db.session.add(backup)
                db.session.commit()
                
                # Run backup in background
                from threading import Thread
                user_id = current_user.id
                thread = Thread(target=create_backup, args=(backup.id, user_id), daemon=True)
                thread.start()
                
                flash('Backup process started successfully. You will be notified when complete.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error initiating backup: {str(e)}', 'danger')
        
        elif action == 'restore_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                # Verify backup exists
                if not verify_backup_exists(backup):
                    flash('Backup file not found', 'danger')
                    return redirect(url_for('backup_management'))
                
                # Run restore in background
                from threading import Thread
                thread = Thread(target=restore_backup, args=(backup.id,), daemon=True)
                thread.start()
                
                flash('Restore process started successfully. The system may be unavailable during restoration.', 'warning')
            except Exception as e:
                flash(f'Error initiating restore: {str(e)}', 'danger')
        
        elif action == 'download_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                if not verify_backup_exists(backup):
                    flash('Backup file not found', 'danger')
                    return redirect(url_for('backup_management'))
                
                # Get backup file
                backup_file = get_backup_file(backup)
                
                # Create a response with the backup file
                decrypt = request.form.get('decrypt') == 'true'
                if not decrypt:
                    response = send_file(
                        backup_file,
                        as_attachment=True,
                        download_name=f"backup_{backup.backup_id}.zip.enc",
                        mimetype='application/octet-stream'
                    )
                else:
                    temp_dir = tempfile.mkdtemp()
                    enc_path = os.path.join(temp_dir, f"{backup.backup_id}.zip.enc")
                    dec_path = os.path.join(temp_dir, f"{backup.backup_id}.zip")
                    with open(enc_path, 'wb') as f:
                        f.write(backup_file.read())
                    cipher = Fernet(BACKUP_CONFIG['encryption_key'].encode())
                    with open(enc_path, 'rb') as f_in, open(dec_path, 'wb') as f_out:
                        f_out.write(cipher.decrypt(f_in.read()))
                    response = send_file(
                        dec_path,
                        as_attachment=True,
                        download_name=f"backup_{backup.backup_id}.zip",
                        mimetype='application/zip'
                    )
                    response.call_on_close(lambda: (os.remove(enc_path), os.remove(dec_path), os.rmdir(temp_dir)))
                
                # Log download activity
                log_audit('download', 'BackupRecord', backup.id, None, {'downloaded_by': current_user.id})
                
                return response
            except Exception as e:
                flash(f'Error downloading backup: {str(e)}', 'danger')
        
        elif action == 'delete_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                # Delete from storage
                delete_backup_file(backup)
                
                # Delete record
                db.session.delete(backup)
                db.session.commit()
                
                flash('Backup deleted successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting backup: {str(e)}', 'danger')
        
        return redirect(url_for('backup_management'))
    
    # Get all backups ordered by most recent
    backups = BackupRecord.query.order_by(BackupRecord.timestamp.desc()).all()
    
    # Get disaster recovery plans
    recovery_plans = DisasterRecoveryPlan.query.all()
    
    return render_template('admin/backup.html', backups=backups, recovery_plans=recovery_plans)

@app.route('/admin/disaster_recovery', methods=['GET', 'POST'])
@login_required
def disaster_recovery():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_recovery_plan':
            try:
                plan = DisasterRecoveryPlan(
                    name=request.form.get('name'),
                    description=request.form.get('description'),
                    recovery_point_objective=int(request.form.get('rpo', 1440)),  # Default 24 hours
                    recovery_time_objective=int(request.form.get('rto', 240)),   # Default 4 hours
                    is_active=True
                )
                db.session.add(plan)
                db.session.commit()
                flash('Disaster recovery plan created successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating recovery plan: {str(e)}', 'danger')
        
        elif action == 'update_recovery_plan':
            plan_id = request.form.get('plan_id')
            plan = DisasterRecoveryPlan.query.get_or_404(plan_id)
            
            try:
                plan.name = request.form.get('name', plan.name)
                plan.description = request.form.get('description', plan.description)
                plan.recovery_point_objective = int(request.form.get('rpo', plan.recovery_point_objective))
                plan.recovery_time_objective = int(request.form.get('rto', plan.recovery_time_objective))
                plan.is_active = request.form.get('is_active', 'off') == 'on'
                db.session.commit()
                flash('Disaster recovery plan updated successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating recovery plan: {str(e)}', 'danger')
        
        elif action == 'test_recovery_plan':
            plan_id = request.form.get('plan_id')
            plan = DisasterRecoveryPlan.query.get_or_404(plan_id)
            
            try:
                # Find most recent backup
                backup = BackupRecord.query.filter_by(status='completed')\
                    .order_by(BackupRecord.timestamp.desc())\
                    .first()
                
                if not backup:
                    flash('No valid backups found for recovery testing', 'danger')
                    return redirect(url_for('disaster_recovery'))
                
                # Run test restore in background
                from threading import Thread
                thread = Thread(target=test_disaster_recovery, args=(plan.id, backup.id), daemon=True)
                thread.start()
                
                flash('Disaster recovery test initiated. You will be notified when complete.', 'info')
            except Exception as e:
                flash(f'Error initiating recovery test: {str(e)}', 'danger')
        
        return redirect(url_for('disaster_recovery'))
    
    # Get all recovery plans
    recovery_plans = DisasterRecoveryPlan.query.all()
    
    return render_template('admin/disaster_recovery.html', recovery_plans=recovery_plans)

@app.route('/admin/backup/status/<int:backup_id>')
@login_required
def backup_status(backup_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    backup = BackupRecord.query.get_or_404(backup_id)
    return jsonify({
        'id': backup.id,
        'status': backup.status,
        'timestamp': backup.timestamp.isoformat(),
        'size_bytes': backup.size_bytes,
        'notes': backup.notes
    })

@app.route('/admin/backup/logs')
@login_required
def backup_logs():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get last 50 backup operations
    backups = BackupRecord.query.order_by(BackupRecord.timestamp.desc()).limit(50).all()
    
    return jsonify([{
        'id': b.id,
        'backup_id': b.backup_id,
        'timestamp': b.timestamp.isoformat(),
        'type': b.backup_type,
        'status': b.status,
        'size_mb': round(b.size_bytes / (1024 * 1024), 2) if b.size_bytes else None,
        'user': b.user.username if b.user else 'System'
    } for b in backups])

# ======================
# BACKUP IMPLEMENTATION
# ======================

def create_backup(backup_id, created_by_user_id=None):
    """Create a database backup in background"""
    with app.app_context():
        backup = db.session.get(BackupRecord, backup_id)  # Updated to use session.get()
        if not backup:
            return
        
        try:
            # Create a temporary file
            temp_dir = tempfile.mkdtemp()
            backup_file = os.path.join(temp_dir, f'backup_{backup.backup_id}.zip')
            
            # Create a ZIP file containing all table data as NDJSON streamed per row
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup each table
                for table_name in BACKUP_CONFIG['tables_to_backup']:
                    try:
                        # Get table data using SQLAlchemy 2.0 syntax with streaming
                        with db.engine.connect() as conn:
                            result = conn.execution_options(stream_results=True).execute(text(f"SELECT * FROM {table_name}"))
                            with zipf.open(f"{table_name}.ndjson", "w") as zf:
                                for row in result:
                                    zf.write((json.dumps(dict(row._mapping), default=str) + "\n").encode("utf-8"))
                    except Exception as e:
                        app.logger.error(f'Error backing up table {table_name}: {str(e)}')
                        continue
                
                # Add metadata
                metadata = {
                    'backup_id': backup.backup_id,
                    'timestamp': datetime.now(timezone.utc).isoformat(),  # Updated to timezone-aware
                    'database_url': str(db.engine.url),
                    'tables_backed_up': BACKUP_CONFIG['tables_to_backup'],
                    'app_version': '1.0.0',
                    'key_id': 'fernet-v1'
                }
                zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
            
            # Calculate checksum
            with open(backup_file, 'rb') as f:
                file_hash = hashlib.sha256()
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    file_hash.update(chunk)
                checksum = file_hash.hexdigest()
            
            # Encrypt the backup
            cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
            with open(backup_file, 'rb') as f:
                encrypted_data = cipher_suite.encrypt(f.read())
            
            encrypted_file = backup_file + '.enc'
            with open(encrypted_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Get file size
            file_size = os.path.getsize(encrypted_file)
            
            # Store backup (local or S3)
            if s3_client:
                # Upload to S3
                s3_key = f'backups/{backup.backup_id}.zip.enc'
                s3_client.upload_file(
                    encrypted_file,
                    BACKUP_CONFIG['s3_bucket'],
                    s3_key,
                    ExtraArgs={
                        'ServerSideEncryption': 'AES256',
                        'ACL': 'private',
                        'Metadata': {
                            'backup-id': backup.backup_id,
                            'checksum': checksum,
                            'created-by': str(created_by_user_id) if created_by_user_id is not None else 'system'
                        }
                    }
                )
                # Verify checksum metadata after upload
                head = s3_client.head_object(Bucket=BACKUP_CONFIG['s3_bucket'], Key=s3_key)
                if head.get('Metadata', {}).get('checksum') != checksum:
                    backup.status = 'failed'
                    backup.notes = 'Checksum mismatch after upload'
                    db.session.commit()
                    raise RuntimeError("Checksum mismatch after upload")
                storage_location = f's3://{BACKUP_CONFIG["s3_bucket"]}/{s3_key}'
            else:
                # Store locally
                local_backup_dir = BACKUP_CONFIG['local_storage_path']
                os.makedirs(local_backup_dir, exist_ok=True)
                local_path = os.path.join(local_backup_dir, f'{backup.backup_id}.zip.enc')
                os.rename(encrypted_file, local_path)
                storage_location = local_path
            
            # Update backup record
            backup.status = 'completed'
            backup.size_bytes = file_size
            backup.storage_location = storage_location
            backup.checksum = checksum
            db.session.commit()
            
            # Clean up
            try:
                os.remove(backup_file)
                if os.path.exists(encrypted_file):
                    os.remove(encrypted_file)
                os.rmdir(temp_dir)
            except:
                pass
            
        except Exception as e:
            app.logger.error(f'Backup failed: {str(e)}', exc_info=True)
            backup.status = 'failed'
            backup.notes = f'Error: {str(e)}'
            db.session.commit()

def restore_backup(backup_id):
    """Restore database from backup"""
    with app.app_context():
        backup = db.session.get(BackupRecord, backup_id)
        if not backup:
            return
        
        try:
            # Get the backup file
            backup_file = get_backup_file(backup)
            if not backup_file:
                backup.status = 'failed'
                backup.notes = 'Backup file not found'
                db.session.commit()
                return
            
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            encrypted_file = os.path.join(temp_dir, 'backup.zip.enc')
            
            # Write the backup data to a temporary file
            with open(encrypted_file, 'wb') as f:
                f.write(backup_file.read())
            
            # Decrypt the backup
            cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
            with open(encrypted_file, 'rb') as f:
                decrypted_data = cipher_suite.decrypt(f.read())
            
            decrypted_file = os.path.join(temp_dir, 'backup.zip')
            with open(decrypted_file, 'wb') as f:
                f.write(decrypted_data)
            
            # Extract and process the ZIP file
            allowed_tables = set(BACKUP_CONFIG['tables_to_backup'])
            with zipfile.ZipFile(decrypted_file, 'r') as z:
                # Read metadata
                metadata = json.loads(z.read('metadata.json').decode('utf-8'))

            for table_name in metadata['tables_backed_up']:
                if table_name not in allowed_tables:
                    continue
                
                ndjson_name = f"{table_name}.ndjson"
                if ndjson_name not in z.namelist():
                    continue
                
                meta = MetaData()
                table = Table(table_name, meta, autoload_with=db.engine)
                
                batch = []
                batch_size = 1000
                with db.engine.begin() as conn:
                    # DATABASE-AGNOSTIC TABLE CLEARING
                    if database_is_postgresql():
                        conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))
                    else:
                        conn.execute(text(f'DELETE FROM "{table_name}"'))
                    
                    with z.open(ndjson_name) as f:
                        for raw_line in f:
                            line = raw_line.decode('utf-8').strip()
                            if not line:
                                continue
                            row = json.loads(line)
                            # Handle special cases (like dates)
                            for key, value in list(row.items()):
                                if value and isinstance(value, str) and value.endswith('+00:00'):
                                    try:
                                        row[key] = datetime.fromisoformat(value)
                                    except:
                                        pass
                            batch.append(row)
                            if len(batch) >= batch_size:
                                conn.execute(table.insert(), batch)
                                batch.clear()
                        if batch:
                            conn.execute(table.insert(), batch)
                         
            # Update backup record
            backup.notes = 'Restore completed successfully'
            db.session.commit()
            
            # Clean up
            try:
                os.remove(encrypted_file)
                os.remove(decrypted_file)
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except:
                pass
            
        except Exception as e:
            app.logger.error(f'Restore failed: {str(e)}', exc_info=True)
            backup.notes = f'Restore error: {str(e)}'
            db.session.commit()

def test_disaster_recovery(plan_id, backup_id):
    """Test disaster recovery plan by restoring to a test database"""
    with app.app_context():
        plan = DisasterRecoveryPlan.query.get(plan_id)
        backup = BackupRecord.query.get(backup_id)
        
        if not plan or not backup:
            return
        
        try:
            # Create a test database URL by appending _test to the main DB name
            original_db_url = db.engine.url
            test_db_url = f"{original_db_url}_recovery_test"
            
            # Create a new engine for the test database
            test_engine = create_engine(test_db_url)
            
            # Create the test database if it doesn't exist
            with test_engine.connect() as conn:
                conn.execute("COMMIT")  # End any open transaction
                try:
                    conn.execute(f"CREATE DATABASE {original_db_url.database}_recovery_test")
                except Exception as e:
                    app.logger.info(f"Test database already exists or couldn't be created: {str(e)}")
            
            # Now connect to the test database
            test_engine.dispose()
            test_engine = create_engine(test_db_url)
            
            # Get the backup file
            backup_file = get_backup_file(backup)
            if not backup_file:
                plan.test_results = "Backup file not found"
                plan.last_tested = datetime.now(timezone.utc)
                db.session.commit()
                return
            
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            encrypted_file = os.path.join(temp_dir, 'backup.zip.enc')
            
            # Write the backup data to a temporary file
            with open(encrypted_file, 'wb') as f:
                f.write(backup_file.read())
            
            # Decrypt the backup
            cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
            with open(encrypted_file, 'rb') as f:
                decrypted_data = cipher_suite.decrypt(f.read())
            
            decrypted_file = os.path.join(temp_dir, 'backup.zip')
            with open(decrypted_file, 'wb') as f:
                f.write(decrypted_data)
            
            # Read and restore from the ZIP file into the test database
            test_metadata = {
                'tables_restored': [],
                'row_counts': {},
                'errors': []
            }
            allowed_tables = set(BACKUP_CONFIG['tables_to_backup'])
            
            with zipfile.ZipFile(decrypted_file, 'r') as z:
                # Read metadata
                metadata = json.loads(z.read('metadata.json').decode('utf-8'))
                
                for table_name in metadata['tables_backed_up']:
                    if table_name not in allowed_tables:
                        app.logger.warning(f"Skipping non-whitelisted table in test restore: {table_name}")
                        continue
                    
                    ndjson_name = f"{table_name}.ndjson"
                    if ndjson_name not in z.namelist():
                        continue
                    
                    meta = MetaData()
                    table = Table(table_name, meta, autoload_with=test_engine)
                    
                    row_count = 0
                    try:
                        with test_engine.begin() as conn:
                            conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))
                            batch = []
                            batch_size = 1000
                            with z.open(ndjson_name) as f:
                                for raw_line in f:
                                    line = raw_line.decode('utf-8').strip()
                                    if not line:
                                        continue
                                    row = json.loads(line)
                                    # Handle special cases (like dates)
                                    for key, value in list(row.items()):
                                        if value and isinstance(value, str) and value.endswith('+00:00'):
                                            try:
                                                row[key] = datetime.fromisoformat(value)
                                            except:
                                                pass
                                    batch.append(row)
                                    if len(batch) >= batch_size:
                                        conn.execute(table.insert(), batch)
                                        row_count += len(batch)
                                        batch.clear()
                                if batch:
                                    conn.execute(table.insert(), batch)
                                    row_count += len(batch)
                        
                        test_metadata['tables_restored'].append(table_name)
                        test_metadata['row_counts'][table_name] = row_count
                    except Exception as e:
                        error_msg = f'Error restoring table {table_name}: {str(e)}'
                        app.logger.error(error_msg)
                        test_metadata['errors'].append(error_msg)
                        continue
            
            # Verification Phase
            verification_results = verify_test_restoration(test_engine, metadata, test_metadata)
            
            # Combine results
            test_results = {
                'backup_id': backup.backup_id,
                'backup_timestamp': backup.timestamp.isoformat(),
                'tables_restored': len(test_metadata['tables_restored']),
                'total_rows_restored': sum(test_metadata['row_counts'].values()),
                'verification_passed': verification_results['success'],
                'verification_details': verification_results,
                'errors': test_metadata['errors']
            }
            
            # Update plan with test results
            plan.last_tested = datetime.now(timezone.utc)
            plan.test_results = json.dumps(test_results, indent=2)
            db.session.commit()
            
            # Clean up
            try:
                os.remove(encrypted_file)
                os.remove(decrypted_file)
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except:
                pass
            
        except Exception as e:
            app.logger.error(f'Disaster recovery test failed: {str(e)}', exc_info=True)
            plan.last_tested = datetime.now(timezone.utc)
            plan.test_results = f"Test failed: {str(e)}"
            db.session.commit()

def verify_test_restoration(test_engine, original_metadata, test_metadata):
    """Verify that the test restoration was successful"""
    verification = {
        'success': True,
        'checks': [],
        'table_counts': {},
        'schema_checks': {}
    }
    
    try:
        # 1. Verify all tables were restored
        with test_engine.connect() as conn:
            # Get list of tables in test database
            result = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            test_tables = {row[0] for row in result}
            
            # Check against original metadata
            for table in original_metadata['tables_backed_up']:
                check = {
                    'table': table,
                    'exists': table in test_tables,
                    'row_count_match': False
                }
                
                if check['exists']:
                    # Get row count in test database
                    count = conn.execute(f'SELECT COUNT(*) FROM {table}').scalar()
                    check['test_row_count'] = count
                    check['backup_row_count'] = test_metadata['row_counts'].get(table, 0)
                    check['row_count_match'] = count == test_metadata['row_counts'].get(table, 0)
                
                verification['table_counts'][table] = check
                verification['checks'].append(f"Table {table} {'exists' if check['exists'] else 'missing'}")
                
                if not check['exists'] or not check['row_count_match']:
                    verification['success'] = False
        
        # 2. Verify schema integrity for key tables
        key_tables = ['users', 'transactions']  # Add your critical tables here
        with test_engine.connect() as conn:
            for table in key_tables:
                if table not in test_tables:
                    continue
                
                # Get column information
                result = conn.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                """)
                columns = {row[0]: row[1] for row in result}
                
                # Check for required columns
                required_columns = {
                    'users': ['id', 'username', 'email', 'password_hash'],
                    'transactions': ['id', 'transaction_number', 'amount']
                }.get(table, [])
                
                schema_check = {
                    'columns_present': all(col in columns for col in required_columns),
                    'missing_columns': [col for col in required_columns if col not in columns],
                    'column_types': columns
                }
                
                verification['schema_checks'][table] = schema_check
                verification['checks'].append(f"Schema check for {table}: {'passed' if schema_check['columns_present'] else 'failed'}")
                
                if not schema_check['columns_present']:
                    verification['success'] = False
        
        # 3. Verify data integrity samples
        sample_verification = verify_sample_data(test_engine)
        verification['sample_checks'] = sample_verification
        verification['checks'].extend(sample_verification['checks'])
        
        if not sample_verification['success']:
            verification['success'] = False
        
        return verification
    
    except Exception as e:
        app.logger.error(f'Verification failed: {str(e)}')
        verification['success'] = False
        verification['error'] = str(e)
        return verification

def verify_sample_data(test_engine):
    """Perform sample data verification on key tables"""
    results = {
        'success': True,
        'checks': [],
        'details': {}
    }
    
    try:
        with test_engine.connect() as conn:
            # 1. Check admin user exists
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").scalar()
            admin_check = admin_count > 0
            results['details']['admin_user_exists'] = admin_check
            results['checks'].append(f"Admin user exists: {'yes' if admin_check else 'no'}")
            if not admin_check:
                results['success'] = False
            
            # 2. Check transaction totals match
            backup_trans_total = conn.execute("SELECT SUM(amount) FROM transactions").scalar() or 0
            results['details']['transaction_total'] = backup_trans_total
            results['checks'].append(f"Transaction total: {backup_trans_total}")
            
            # 3. Verify at least one record in each key table
            key_tables = ['users', 'transactions', 'customers', 'employees']
            for table in key_tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").scalar()
                    check = count > 0
                    results['details'][f'{table}_has_data'] = check
                    results['checks'].append(f"Table {table} has data: {'yes' if check else 'no'}")
                    if not check:
                        results['success'] = False
                except:
                    results['details'][f'{table}_has_data'] = False
                    results['checks'].append(f"Table {table} check failed")
                    results['success'] = False
            
            # 4. Verify referential integrity
            ref_checks = [
                ("SELECT COUNT(*) FROM transactions t LEFT JOIN users u ON t.user_id = u.id WHERE u.id IS NULL", 'transactions.user_id -> users.id'),
                ("SELECT COUNT(*) FROM payroll p LEFT JOIN employees e ON p.employee_id = e.id WHERE e.id IS NULL", 'payroll.employee_id -> employees.id')
            ]
            
            for query, description in ref_checks:
                try:
                    bad_records = conn.execute(query).scalar()
                    check = bad_records == 0
                    results['details'][f'ref_check_{description}'] = check
                    results['checks'].append(f"Referential integrity {description}: {'valid' if check else f'{bad_records} bad records'}")
                    if not check:
                        results['success'] = False
                except:
                    results['details'][f'ref_check_{description}'] = False
                    results['checks'].append(f"Referential check failed for {description}")
                    results['success'] = False
        
        return results
    
    except Exception as e:
        app.logger.error(f'Sample data verification failed: {str(e)}')
        results['success'] = False
        results['error'] = str(e)
        return results

def verify_backup_exists(backup):
    """Verify that the backup file exists in storage"""
    if not backup.storage_location:
        return False
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return False
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False
    else:
        return os.path.exists(backup.storage_location)

def get_backup_file(backup):
    """Get the backup file from storage"""
    if not backup.storage_location:
        return None
    
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return None
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            
            # Download from S3
            s3_client.download_fileobj(bucket, key, temp_file)
            temp_file.close()
            
            # Return file object
            return open(temp_file.name, 'rb')
        except ClientError as e:
            app.logger.error(f'Error downloading backup from S3: {str(e)}')
            return None
    else:
        try:
            return open(backup.storage_location, 'rb')
        except IOError as e:
            app.logger.error(f'Error opening local backup file: {str(e)}')
            return None

def delete_backup_file(backup):
    """Delete the backup file from storage"""
    if not backup.storage_location:
        return
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            s3_client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            app.logger.error(f'Error deleting backup from S3: {str(e)}')
    else:
        try:
            os.remove(backup.storage_location)
        except OSError as e:
            app.logger.error(f'Error deleting local backup file: {str(e)}')


def scheduled_backup():
    """Create a scheduled backup"""
    with app.app_context():
        try:
            # Create backup record
            backup = BackupRecord(
                backup_type='scheduled',
                notes='Automated scheduled backup',
                status='in_progress'
            )
            db.session.add(backup)
            db.session.commit()
            
            # Run backup
            create_backup(backup.id)
        except Exception as e:
            app.logger.error(f'Error in scheduled backup: {str(e)}')

# Initialize scheduler
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_backup, 'cron', hour=2, minute=0)  # Daily at 2 AM
    scheduler.start()

# ======================
# MONEY MANAGEMENT ROUTES
# ======================

@app.route('/admin/money')
@login_required
def manage_money():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    return render_template('admin/money.html',
                        drawings=Transaction.query.filter_by(transaction_type='drawing').order_by(Transaction.created_at.desc()).all(),
                        expenses=Expense.query.order_by(Expense.created_at.desc()).all(),
                        purchases=Purchase.query.order_by(Purchase.created_at.desc()).all(),
                        payroll=Payroll.query.order_by(Payroll.created_at.desc()).all(),
                        debtors=Debtor.query.order_by(Debtor.amount_owed.desc()).all(),
                        employees=Employee.query.all(),
                        current_date=get_eat_now().date())

# ==============
# DRAWING ROUTES
# ==============

@app.route('/admin/add_drawing', methods=['POST'])
@login_required
def add_drawing():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='drawing',  # Changed from 'expense' to 'drawing'
            amount=amount,
            user_id=current_user.id,
            notes=f"Owner's drawing: {description}"
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Payroll added and transaction recorded'})
    except ValueError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Invalid data provided'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500


@app.route('/admin/pay_payroll/<int:id>', methods=['POST'])
@login_required
def pay_payroll(id):
    if current_user.role not in ('admin', 'accountant'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    payroll = Payroll.query.get_or_404(id)
    try:
        # Ensure DB schema for payroll_payments has expected columns (helps when migrations weren't run)
        try:
            with db.engine.connect() as conn:
                # For SQLite this returns rows with columns: cid, name, type, notnull, dflt_value, pk
                res = conn.execute(text("PRAGMA table_info('payroll_payments')"))
                cols = [r[1] for r in res.fetchall()]
                if 'paid_by' not in cols:
                    app.logger.info('Schema fix: adding missing column payroll_payments.paid_by')
                    conn.execute(text('ALTER TABLE payroll_payments ADD COLUMN paid_by INTEGER'))
        except Exception as schema_exc:
            # Log but continue; if table missing entirely the normal flow will error and be returned to client
            current_app.logger.debug(f"Schema check/alter failed: {schema_exc}")
        amount = float(request.form.get('amount', 0))
        notes = request.form.get('notes', '')
        # allow user to pass payment_date (YYYY-MM-DD)
        payment_date_str = request.form.get('payment_date')

        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        # Calculate total already paid
        total_paid = sum([p.amount for p in payroll.payments]) if payroll.payments else 0.0
        remaining = payroll.amount - total_paid

        if amount > remaining + 0.0001:
            return jsonify({'success': False, 'error': f'Amount exceeds remaining balance (Ksh {remaining:.2f})'}), 400

        # Parse payment date if provided, otherwise use now
        if payment_date_str:
            try:
                pd = datetime.strptime(payment_date_str, '%Y-%m-%d')
                payment_dt = datetime(pd.year, pd.month, pd.day, tzinfo=timezone.utc)
            except Exception:
                payment_dt = datetime.now(timezone.utc)
        else:
            payment_dt = datetime.now(timezone.utc)

        payment = PayrollPayment(
            payroll_id=payroll.id,
            amount=amount,
            paid_by=current_user.id,
            payment_date=payment_dt,
            notes=notes
        )
        db.session.add(payment)
        db.session.flush()

        # Create transaction record for the payroll payment
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='payroll_payment',
            amount=amount,
            user_id=current_user.id,
            reference_id=payroll.id,
            notes=f"Payroll payment for {payroll.payroll_number}: {notes}"
        )
        db.session.add(transaction)

        # Update payroll status if fully paid
        total_paid += amount
        if abs(total_paid - payroll.amount) < 0.005 or total_paid >= payroll.amount:
            payroll.status = 'paid'
        else:
            payroll.status = 'partial'

        db.session.commit()
        return jsonify({'success': True, 'message': 'Payment recorded successfully', 'remaining': round(payroll.amount - total_paid, 2)})
    except ValueError:
        db.session.rollback()
        current_app.logger.exception(f"ValueError processing payroll payment {id}")
        return jsonify({'success': False, 'error': 'Invalid amount provided'}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error processing payroll payment {id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred while processing payment'}), 500
        db.session.commit()
        return jsonify({'success': True, 'message': 'Drawing added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/admin/update_drawing/<int:id>', methods=['POST'])
@login_required
def update_drawing(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    drawing = Transaction.query.get_or_404(id)
    try:
        drawing.amount = float(request.form.get('amount'))
        description = request.form.get('description')
        drawing.notes = f"Owner's drawing: {description}" if description is not None else drawing.notes
        db.session.commit()
        return jsonify({'success': True, 'message': 'Drawing updated successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/delete_drawing/<int:id>', methods=['POST'])
@login_required
def delete_drawing(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    drawing = Transaction.query.get_or_404(id)
    try:
        db.session.delete(drawing)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Drawing deleted successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

# =============
# BILLS ROUTES
# =============

@app.route('/admin/add_bill', methods=['POST'])
@login_required
def add_bill():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        expense = Expense(
            expense_number=generate_expense_number(),
            expense_type=request.form.get('bill_type'),
            amount=float(request.form.get('amount')),
            user_id=current_user.id,
            description=request.form.get('description'),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date(),
            status='pending'
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill added successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/update_bill/<int:id>', methods=['POST'])
@login_required
def update_bill(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        bill.expense_type = request.form.get('bill_type')
        bill.amount = float(request.form.get('amount'))
        bill.description = request.form.get('description')
        bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill updated successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/delete_bill/<int:id>', methods=['POST'])
@login_required
def delete_bill(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        db.session.delete(bill)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill deleted successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/pay_bill/<int:id>', methods=['POST'])
@login_required
def pay_bill(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        bill.status = 'paid'
        bill.paid_date = get_eat_now().date()
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='expense',
            amount=bill.amount,
            user_id=current_user.id,
            reference_id=bill.id,
            notes=f"Bill payment: {bill.expense_type}"
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill payment recorded successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

# ================
# PURCHASE ROUTES
# ================

@app.route('/admin/add_purchase', methods=['POST'])
@login_required
def add_purchase():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        purchase = Purchase(
            purchase_number=generate_purchase_number(),
            purchase_type=request.form.get('purchase_type'),
            amount=float(request.form.get('amount')),
            purchase_date=datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date(),
            supplier=request.form.get('supplier'),
            description=request.form.get('description'),
            user_id=current_user.id
        )
        db.session.add(purchase)
        db.session.flush()
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='purchase',
            amount=purchase.amount,
            user_id=current_user.id,
            reference_id=purchase.id,
            notes=f"Purchase: {purchase.purchase_type}"
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Purchase added successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/update_purchase/<int:id>', methods=['POST'])
@login_required
def update_purchase(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    purchase = Purchase.query.get_or_404(id)
    try:
        purchase.purchase_type = request.form.get('purchase_type')
        purchase.amount = float(request.form.get('amount'))
        purchase.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        purchase.supplier = request.form.get('supplier')
        purchase.description = request.form.get('description')
        db.session.commit()
        return jsonify({'success': True, 'message': 'Purchase updated successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/delete_purchase/<int:id>', methods=['POST'])
@login_required
def delete_purchase(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    purchase = Purchase.query.get_or_404(id)
    try:
        # Delete associated transaction first
        Transaction.query.filter_by(transaction_type='purchase', reference_id=id).delete()
        db.session.delete(purchase)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Purchase deleted successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500
# ===============
# PAYROLL ROUTES (Updated)
# ===============

@app.route('/admin/add_payroll', methods=['POST'])
@login_required
def add_payroll():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        # Validate required fields
        if not all([request.form.get('employee_id'), request.form.get('amount'), request.form.get('payment_date')]):
            return jsonify({'success': False, 'error': 'Please fill all required fields'}), 400

        employee = db.session.get(Employee, request.form.get('employee_id'))
        if not employee:
            return jsonify({'success': False, 'error': 'Employee not found'}), 404

        amount = float(request.form.get('amount'))
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        
        payroll = Payroll(
            payroll_number=generate_payroll_number(),
            employee_id=employee.id,
            amount=amount,
            payment_date=payment_date,
            pay_period=request.form.get('pay_period', 'monthly'),
            notes=request.form.get('notes', ''),
            status='paid',  # Assuming immediate payment
            user_id=current_user.id
        )
        db.session.add(payroll)
        db.session.flush()
        
        # Create transaction record (as expense)
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='expense',  # Changed from 'payroll' to 'expense'
            amount=amount,
            user_id=current_user.id,
            reference_id=payroll.id,
            notes=f"Payroll payment for {employee.name}",
            created_at=get_eat_now()
        )
        db.session.add(transaction)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Payroll payment added successfully'})
    except ValueError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Invalid data format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/update_payroll/<int:id>', methods=['POST'])
@login_required
def update_payroll(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    payroll = Payroll.query.get_or_404(id)
    try:
        if not all([request.form.get('employee_id'), request.form.get('amount'), request.form.get('payment_date')]):
            return jsonify({'success': False, 'error': 'Please fill all required fields'}), 400

        employee = Employee.query.get(request.form.get('employee_id'))
        if not employee:
            return jsonify({'success': False, 'error': 'Employee not found'}), 404

        amount = float(request.form.get('amount'))
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        # Update payroll
        payroll.employee_id = employee.id
        payroll.amount = amount
        payroll.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        payroll.pay_period = request.form.get('pay_period', payroll.pay_period)
        payroll.notes = request.form.get('notes', payroll.notes)
        
        # Update associated transaction
        transaction = Transaction.query.filter_by(reference_id=id).first()
        if transaction:
            transaction.amount = amount
            transaction.notes = f"Payroll payment for {employee.name}"
            transaction.created_at = get_eat_now()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Payroll updated successfully'})
    except ValueError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Invalid data format'}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

# Add a new route to get employee salary
@app.route('/admin/get_employee_salary/<int:employee_id>')
@login_required
def get_employee_salary(employee_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    employee = Employee.query.get_or_404(employee_id)
    return jsonify({'salary': employee.salary})

# ================
# DEBTOR ROUTES
# ================
@app.route('/admin/add_debtor', methods=['POST'])
@login_required
def add_debtor():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        name = (request.form.get('name') or '').strip()
        contact = (request.form.get('contact') or '').strip() or None
        email = (request.form.get('email') or '').strip() or None
        total_debt_raw = request.form.get('total_debt')
        last_payment_date = request.form.get('last_payment_date') or None
        next_payment_date = request.form.get('next_payment_date') or None
        notes = (request.form.get('notes') or '').strip() or None

        if not name:
            return bad_request('Name is required')
        if total_debt_raw is None or str(total_debt_raw).strip() == '':
            return bad_request('Total debt is required')
        try:
            total_debt = float(total_debt_raw)
        except (TypeError, ValueError):
            return bad_request('Invalid total debt')
        if total_debt < 0:
            return bad_request('Total debt must be non-negative')

        def parse_date(value):
            if not value:
                return None
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except Exception:
                return None

        debtor = Debtor(
            name=name,
            contact=contact,
            email=email,
            Total_debt=total_debt,
            amount_paid=0.0,
            amount_owed=total_debt,
            last_payment_date=parse_date(last_payment_date),
            next_payment_date=parse_date(next_payment_date)
        )
        db.session.add(debtor)
        db.session.commit()

        log_audit(
            'create',
            table='debtor',
            record_id=debtor.id,
            changes={'action': 'add_debtor', 'name': name, 'total_debt': total_debt, 'contact': contact, 'email': email}
        )

        return jsonify({'success': True, 'id': debtor.id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"add_debtor failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
def add_debtor():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        name = (request.form.get('name') or '').strip()
        contact = (request.form.get('contact') or '').strip() or None
        email = (request.form.get('email') or '').strip() or None
        total_debt_raw = request.form.get('total_debt')
        last_payment_date = request.form.get('last_payment_date') or None
        next_payment_date = request.form.get('next_payment_date') or None
        notes = (request.form.get('notes') or '').strip() or None

        if not name:
            return bad_request('Name is required')
        if total_debt_raw is None or str(total_debt_raw).strip() == '':
            return bad_request('Total debt is required')
        try:
            total_debt = float(total_debt_raw)
        except (TypeError, ValueError):
            return bad_request('Invalid total debt')
        if total_debt < 0:
            return bad_request('Total debt must be non-negative')

        def parse_date(value):
            if not value:
                return None
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except Exception:
                return None

        debtor = Debtor(
            name=name,
            contact=contact,
            email=email,
            Total_debt=total_debt,
            amount_paid=0.0,
            amount_owed=total_debt,
            last_payment_date=parse_date(last_payment_date),
            next_payment_date=parse_date(next_payment_date)
        )
        db.session.add(debtor)
        db.session.commit()

        log_audit(
            'create',
            table='debtor',
            record_id=debtor.id,
            changes={'action': 'add_debtor', 'name': name, 'total_debt': total_debt, 'contact': contact, 'email': email}
        )

        return jsonify({'success': True, 'id': debtor.id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"add_debtor failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        # Validate required fields
        if not all([request.form.get('name'), request.form.get('total_debt')]):
            return jsonify({'success': False, 'error': 'Name and total debt are required'}), 400

        total_debt = float(request.form.get('total_debt'))
        if total_debt <= 0:
            return jsonify({'success': False, 'error': 'Total debt must be positive'}), 400

        # Create new debtor
        debtor = Debtor(
            name=request.form.get('name'),
            contact=request.form.get('contact', ''),
            email=request.form.get('email', ''),
            Total_debt=total_debt,
            amount_paid=0.0,  # Initialize with 0
            amount_owed=total_debt,  # Initially equals total debt
            last_payment_date=datetime.strptime(request.form.get('last_payment_date'), '%Y-%m-%d').date() if request.form.get('last_payment_date') else None,
            next_payment_date=datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date() if request.form.get('next_payment_date') else None,
            notes=request.form.get('notes', '')
        )
        
        db.session.add(debtor)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Debtor added successfully'})
    except ValueError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Invalid amount or date format'}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/add_debtor_payment/<int:debtor_id>', methods=['POST'])
@login_required
def add_debtor_payment(debtor_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    debtor = Debtor.query.get_or_404(debtor_id)
    try:
        if not all([request.form.get('amount'), request.form.get('payment_date')]):
            return jsonify({'success': False, 'error': 'Amount and payment date are required'}), 400

        payment_amount = float(request.form.get('amount'))
        if payment_amount <= 0:
            return jsonify({'success': False, 'error': 'Payment amount must be positive'}), 400

        if payment_amount > debtor.amount_owed:
            return jsonify({'success': False, 'error': 'Payment amount exceeds owed amount'}), 400

        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        
        # Update debtor records
        debtor.amount_paid += payment_amount
        debtor.amount_owed = debtor.Total_debt - debtor.amount_paid
        debtor.last_payment_date = payment_date
        
        # Create payment record
        payment = DebtorPayment(
            debtor_id=debtor_id,
            amount=payment_amount,
            payment_date=payment_date,
            payment_method=request.form.get('payment_method', 'cash'),
            notes=request.form.get('notes', ''),
            user_id=current_user.id
        )
        db.session.add(payment)
        db.session.flush()
        
        # Create transaction record
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='income',
            amount=payment_amount,
            user_id=current_user.id,
            reference_id=payment.id,
            notes=f"Payment from {debtor.name}",
            created_at=get_eat_now()
        )
        db.session.add(transaction)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'amount_paid': debtor.amount_paid,
            'amount_owed': debtor.amount_owed
        })
    except ValueError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Invalid amount or date format'}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/admin/update_debtor/<int:id>', methods=['POST'])
@login_required
def update_debtor(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    debtor = Debtor.query.get_or_404(id)
    try:
        debtor.name = request.form.get('name')
        debtor.contact = request.form.get('contact', debtor.contact)
        debtor.email = request.form.get('email', debtor.email)
        debtor.Total_debt = float(request.form.get('total_debt'))
        debtor.amount_owed = debtor.Total_debt - debtor.amount_paid
        # Optional fields
        if request.form.get('last_payment_date'):
            debtor.last_payment_date = datetime.strptime(request.form.get('last_payment_date'), '%Y-%m-%d').date()
        if request.form.get('next_payment_date'):
            debtor.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        if 'notes' in request.form:
            debtor.notes = request.form.get('notes', debtor.notes)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Debtor updated successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500


@app.route('/admin/delete_debtor/<int:id>', methods=['POST'])
@login_required
def delete_debtor(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    debtor = Debtor.query.get_or_404(id)
    try:
        # Only delete the debtor, payments and transactions remain
        db.session.delete(debtor)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Debtor deleted successfully'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500
    
# =====================
# TRANSACTION ROUTES
# =====================

@app.route('/admin/delete_transaction/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    transaction = Transaction.query.get_or_404(id)
    try:
        # Handle different transaction types
        if transaction.transaction_type == 'purchase':
            Purchase.query.filter_by(id=transaction.reference_id).delete()
        elif transaction.transaction_type == 'payroll':
            Payroll.query.filter_by(id=transaction.reference_id).delete()
        elif transaction.transaction_type == 'debtor_payment':
            DebtorPayment.query.filter_by(id=transaction.reference_id).delete()
        
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

# ========================
# PENDING PAYMENTS CHECK
# =======================
@app.route('/admin/check_pending_payments')
@login_required
def check_pending_payments():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    today = get_eat_now().date()
    
    # Pending bills (status is pending and due date is today or passed)
    pending_bills = Expense.query.filter(
        Expense.status == 'pending',
        Expense.due_date <= today
    ).count()
    
    # Pending payroll (payment date is today or passed)
    pending_payroll = Payroll.query.filter(
        Payroll.payment_date <= today
    ).count()
    
    # Pending debtor payments (next payment date is today or passed)
    pending_debtor_payments = Debtor.query.filter(
        Debtor.next_payment_date <= today
    ).count()
    
    total_pending = pending_bills + pending_payroll + pending_debtor_payments
    
    return jsonify({
        'count': total_pending,
        'pending_bills': pending_bills,
        'pending_payroll': pending_payroll,
        'pending_debtor_payments': pending_debtor_payments
    })
@app.route('/admin/money/summary')
@login_required
def money_summary():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Calculate totals
        total_income = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.transaction_type == 'income'
        ).scalar() or 0

        total_expenses = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.transaction_type.in_(['expense', 'drawing', 'purchase', 'payroll'])
        ).scalar() or 0

        net_profit = total_income - total_expenses
        
        return jsonify({
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/dosage', methods=['GET', 'POST'])
@login_required
def manage_dosage():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                dosage = DrugDosage(
                    drug_id=request.form.get('drug_id'),
                    indication=request.form.get('indication'),
                    contraindication=request.form.get('contraindication'),
                    interaction=request.form.get('interaction'),
                    side_effects=request.form.get('side_effects'),
                    dosage_peds=request.form.get('dosage_peds'),
                    dosage_adults=request.form.get('dosage_adults'),
                    dosage_geriatrics=request.form.get('dosage_geriatrics'),
                    important_notes=request.form.get('important_notes')
                )
                db.session.add(dosage)
                db.session.commit()
                
                log_audit('create', 'DrugDosage', dosage.id, None, {
                    'drug_id': dosage.drug_id,
                    'indication': dosage.indication,
                    'contraindication': dosage.contraindication,
                    'interaction': dosage.interaction,
                    'side_effects': dosage.side_effects,
                    'dosage_peds': dosage.dosage_peds,
                    'dosage_adults': dosage.dosage_adults,
                    'dosage_geriatrics': dosage.dosage_geriatrics,
                    'important_notes': dosage.important_notes
                })
                
                flash('Dosage information added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding dosage information: {str(e)}', 'danger')
        
        elif action == 'edit':
            dosage_id = request.form.get('dosage_id')
            dosage = DrugDosage.query.get(dosage_id)
            if dosage:
                try:
                    old_values = {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    }
                    
                    dosage.indication = request.form.get('indication')
                    dosage.contraindication = request.form.get('contraindication')
                    dosage.interaction = request.form.get('interaction')
                    dosage.side_effects = request.form.get('side_effects')
                    dosage.dosage_peds = request.form.get('dosage_peds')
                    dosage.dosage_adults = request.form.get('dosage_adults')
                    dosage.dosage_geriatrics = request.form.get('dosage_geriatrics')
                    dosage.important_notes = request.form.get('important_notes')
                    
                    db.session.commit()
                    
                    log_audit('update', 'DrugDosage', dosage.id, old_values, {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    })
                    
                    flash('Dosage information updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating dosage information: {str(e)}', 'danger')
            else:
                flash('Dosage information not found', 'danger')
        
        elif action == 'delete':
            dosage_id = request.form.get('dosage_id')
            dosage = DrugDosage.query.get(dosage_id)
            if dosage:
                try:
                    log_audit('delete', 'DrugDosage', dosage.id, {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    }, None)
                    
                    db.session.delete(dosage)
                    db.session.commit()
                    flash('Dosage information deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting dosage information: {str(e)}', 'danger')
            else:
                flash('Dosage information not found', 'danger')
        
        return redirect(url_for('manage_dosage'))
    
    dosages = DrugDosage.query.join(Drug).all()
    drugs = Drug.query.all()
    
    return render_template('admin/dosage.html', dosages=dosages, drugs=drugs)

@app.route('/admin/dosage/<int:dosage_id>')
@login_required
def get_dosage(dosage_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    dosage = DrugDosage.query.get_or_404(dosage_id)
    
    return jsonify({
        'id': dosage.id,
        'drug': {
            'id': dosage.drug.id,
            'drug_number': dosage.drug.drug_number,
            'name': dosage.drug.name
        },
        'indication': dosage.indication,
        'contraindication': dosage.contraindication,
        'interaction': dosage.interaction,
        'side_effects': dosage.side_effects,
        'dosage_peds': dosage.dosage_peds,
        'dosage_adults': dosage.dosage_adults,
        'dosage_geriatrics': dosage.dosage_geriatrics,
        'important_notes': dosage.important_notes
    })

@app.route('/admin/drugs/without-dosage')
@login_required
def get_drugs_without_dosage():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get drugs that don't have dosage information
    drugs = Drug.query.filter(~Drug.dosage.any()).all()
    
    return jsonify([{
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name
    } for drug in drugs])

@app.route('/admin/drugs/<int:drug_id>/dosage')
@login_required
def get_drug_dosage(drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    dosage = DrugDosage.query.filter_by(drug_id=drug.id).first()
    
    return jsonify({
        'drug': {
            'id': drug.id,
            'name': drug.name,
            'drug_number': drug.drug_number
        },
        'dosage': {
            'indication': dosage.indication if dosage else None,
            'contraindication': dosage.contraindication if dosage else None,
            'interaction': dosage.interaction if dosage else None,
            'side_effects': dosage.side_effects if dosage else None,
            'dosage_peds': dosage.dosage_peds if dosage else None,
            'dosage_adults': dosage.dosage_adults if dosage else None,
            'dosage_geriatrics': dosage.dosage_geriatrics if dosage else None,
            'important_notes': dosage.important_notes if dosage else None
        } if dosage else None
    })

@app.before_request
def log_request_info():
    """Log detailed information about each request"""
    if request.method == 'POST':
        app.logger.info(f"POST Request to: {request.path}")
        app.logger.info(f"Headers: {dict(request.headers)}")
        app.logger.info(f"Form data: {dict(request.form)}")
        app.logger.info(f"JSON data: {request.get_json(silent=True)}")
        
# Admin Patient Management Routes
@app.route('/admin/patients', methods=['GET'])
@login_required
def manage_patients():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Handle date filtering
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query with all necessary relationships
    query = Patient.query\
        .outerjoin(PatientLab)\
        .outerjoin(PatientService)\
        .outerjoin(Prescription)\
        .outerjoin(PatientDiagnosis)\
        .options(
            db.joinedload(Patient.labs).joinedload(PatientLab.test),
            db.joinedload(Patient.services).joinedload(PatientService.service),
            db.joinedload(Patient.prescriptions).joinedload(Prescription.items),
            db.joinedload(Patient.diagnoses)
        )
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Patient.created_at >= start_date)
        except ValueError:
            flash('Invalid start date format', 'danger')
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Patient.created_at <= end_date)
        except ValueError:
            flash('Invalid end date format', 'danger')
    
    patients = query.order_by(Patient.created_at.desc()).distinct().all()
    
    # Calculate summary totals
    total_lab_amount = 0
    total_service_amount = 0
    total_drug_amount = 0
    
    for patient in patients:
        # Lab tests total
        for lab in patient.labs:
            total_lab_amount += lab.test.price
        
        # Services total (assuming you have a PatientService model)
        for service in patient.services:
            total_service_amount += service.service.price
        
        # Prescriptions total
        for prescription in patient.prescriptions:
            for item in prescription.items:
                total_drug_amount += item.drug.selling_price * item.quantity
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                patient_type = request.form.get('patient_type')
                patient_number = generate_patient_number(patient_type)
                
                patient = Patient(
                    op_number=patient_number if patient_type == 'OP' else None,
                    ip_number=patient_number if patient_type == 'IP' else None,
                    name=Config.encrypt_data_static(request.form.get('name')),
                    age=int(request.form.get('age')) if request.form.get('age') else None,
                    gender=request.form.get('gender'),
                    address=Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None,
                    phone=Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None,
                    nok_name=Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None,
                    nok_contact=Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None,
                    chief_complaints=request.form.get('chief_complaints'),
                    diagnosis=request.form.get('diagnosis'),
                    tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                    status='active'
                )
                db.session.add(patient)
                db.session.commit()
                
                log_audit('create', 'Patient', patient.id, None, {
                    'patient_number': patient_number,
                    'name': request.form.get('name'),
                    'age': request.form.get('age'),
                    'gender': request.form.get('gender')
                })
                
                flash('Patient added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding patient: {str(e)}', 'danger')
        
        elif action == 'edit':
            patient_id = request.form.get('patient_id')
            patient = Patient.query.get(patient_id)
            if patient:
                try:
                    old_values = {
                        'name': Config.decrypt_data_static(patient.name),
                        'age': patient.age,
                        'gender': patient.gender,
                        'address': Config.decrypt_data_static(patient.address),
                        'phone': Config.decrypt_data_static(patient.phone),
                        'nok_name': Config.decrypt_data_static(patient.nok_name),
                        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
                        'chief_complaints': patient.chief_complaints,
                        'diagnosis': patient.diagnosis,
                        'tca': patient.tca,
                        'status': patient.status
                    }
                    
                    patient.name = Config.encrypt_data_static(request.form.get('name'))
                    patient.age = int(request.form.get('age')) if request.form.get('age') else None
                    patient.gender = request.form.get('gender')
                    patient.address = Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None
                    patient.phone = Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None
                    patient.nok_name = Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None
                    patient.nok_contact = Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None
                    patient.chief_complaints = request.form.get('chief_complaints')
                    patient.diagnosis = request.form.get('diagnosis')
                    patient.tca = datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None
                    patient.status = request.form.get('status')
                    
                    db.session.commit()
                    
                    log_audit('update', 'Patient', patient.id, old_values, {
                        'name': request.form.get('name'),
                        'age': request.form.get('age'),
                        'gender': request.form.get('gender'),
                        'address': request.form.get('address'),
                        'phone': request.form.get('phone'),
                        'nok_name': request.form.get('nok_name'),
                        'nok_contact': request.form.get('nok_contact'),
                        'chief_complaints': request.form.get('chief_complaints'),
                        'diagnosis': request.form.get('diagnosis'),
                        'tca': request.form.get('tca'),
                        'status': request.form.get('status')
                    })
                    
                    flash('Patient updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating patient: {str(e)}', 'danger')
            else:
                flash('Patient not found', 'danger')
        
        return redirect(url_for('manage_patients'))
    
    lab_tests = LabTest.query.all()
    services = Service.query.all()
    
    return render_template('admin/patients.html',
        patients=patients,
        lab_tests=lab_tests,
        services=services,
        total_lab_amount=total_lab_amount,
        total_service_amount=total_service_amount,
        total_drug_amount=total_drug_amount,
        total_amount=total_lab_amount + total_service_amount + total_drug_amount
    )

@app.route('/admin/patients/<int:patient_id>')
@login_required
def get_patient(patient_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    
    return jsonify({
        'id': patient.id,
        'op_number': patient.op_number,
        'ip_number': patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender,
        'address': Config.decrypt_data_static(patient.address),
        'phone': Config.decrypt_data_static(patient.phone),
        'nok_name': Config.decrypt_data_static(patient.nok_name),
        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
        'chief_complaints': patient.chief_complaints,
        'diagnosis': patient.diagnosis,
        'tca': patient.tca.strftime('%Y-%m-%d') if patient.tca else None,
        'status': patient.status
    })

@app.route('/admin/patients/<int:patient_id>/details')
@login_required
def patient_details(patient_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    
    # Calculate financial totals
    total_lab_amount = sum(lab.test.price for lab in patient.labs)
    total_service_amount = sum(service.service.price for service in patient.services)
    total_drug_amount = sum(
        item.drug.selling_price * item.quantity 
        for prescription in patient.prescriptions 
        for item in prescription.items
    )
    
    return jsonify({
        'patient_number': patient.op_number or patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender,
        'type': 'OP' if patient.op_number else 'IP',
        'address': Config.decrypt_data_static(patient.address),
        'phone': Config.decrypt_data_static(patient.phone),
        'nok_name': Config.decrypt_data_static(patient.nok_name),
        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
        'complaints': patient.chief_complaints,
        'diagnosis': patient.diagnosis,
        'treatment': patient.treatment,
        'tca': patient.tca.strftime('%Y-%m-%d') if patient.tca else None,
        'status': patient.status,
        'total_lab_amount': total_lab_amount,
        'total_service_amount': total_service_amount,
        'total_drug_amount': total_drug_amount,
        'total_amount': total_lab_amount + total_service_amount + total_drug_amount,
        'lab_tests': [{
            'id': lab.id,
            'name': lab.test.name,
            'price': lab.test.price,
            'results': lab.results,
            'comments': lab.comments,
            'date': lab.created_at.strftime('%Y-%m-%d')
        } for lab in patient.labs],
        'services': [{
            'id': service.id,
            'name': service.service.name,
            'price': service.service.price,
            'notes': service.notes,
            'date': service.created_at.strftime('%Y-%m-%d')
        } for service in patient.services],
        'prescriptions': [{
            'id': item.id,
            'drug_name': item.drug.name,
            'quantity': item.quantity,
            'unit_price': item.drug.selling_price,
            'status': item.status,
            'date': prescription.created_at.strftime('%Y-%m-%d')
        } for prescription in patient.prescriptions for item in prescription.items]
    })
    
# Medical Tests Management
@app.route('/admin/medical-tests')
@login_required
def manage_tests():
    if current_user.role != 'admin':
        abort(403)
    
    services = Service.query.order_by(Service.name).all()
    lab_tests = LabTest.query.order_by(LabTest.name).all()
    imaging_tests = ImagingTest.query.order_by(ImagingTest.name).all()
    
    return render_template('admin/medical_tests.html', 
                         services=services,
                         lab_tests=lab_tests,
                         imaging_tests=imaging_tests)

# Service CRUD
@app.route('/admin/services/add', methods=['POST'])
@limiter.limit("10 per minute")
@admin_required_json
def add_service():
    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    service = Service(name=name, price=float(price), description=description)
    try:
        db.session.add(service)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'add_service failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('add_service', 'Service', service.id, None, {
            'name': service.name,
            'price': service.price
        })
    except Exception as e:
        current_app.logger.error(f'audit add_service failed: {str(e)}', exc_info=True)

    return success_response({'id': service.id, 'name': service.name, 'price': service.price, 'description': service.description}, status=201)

@app.route('/admin/services/<int:id>')
@limiter.limit("60 per minute")
@admin_required_json
def get_service(id):
    service = Service.query.get(id)
    if not service:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return success_response({
        'id': service.id,
        'name': service.name,
        'price': service.price,
        'description': service.description
    })

@app.route('/admin/services/<int:id>/update', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def update_service(id):
    service = Service.query.get(id)
    if not service:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    old_data = {
        'name': service.name,
        'price': service.price,
        'description': service.description
    }

    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    try:
        service.name = name
        service.price = float(price)
        service.description = description
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'update_service failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('update_service', 'Service', service.id, old_data, {
            'name': service.name,
            'price': service.price,
            'description': service.description
        })
    except Exception as e:
        current_app.logger.error(f'audit update_service failed: {str(e)}', exc_info=True)

    return success_response({'id': service.id, 'name': service.name, 'price': service.price, 'description': service.description})

@app.route('/admin/services/<int:id>/delete', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def delete_service(id):
    service = Service.query.get(id)
    if not service:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    try:
        db.session.delete(service)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'delete_service failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('delete_service', 'Service', service.id, {'name': service.name, 'price': service.price}, None)
    except Exception as e:
        current_app.logger.error(f'audit delete_service failed: {str(e)}', exc_info=True)

    return success_response()

# Lab Test CRUD
@app.route('/admin/lab-tests/add', methods=['POST'])
@limiter.limit("10 per minute")
@admin_required_json
def add_lab_test():
    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    lab_test = LabTest(name=name, price=float(price), description=description)
    try:
        db.session.add(lab_test)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'add_lab_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('add_lab_test', 'LabTest', lab_test.id, None, {
            'name': lab_test.name,
            'price': lab_test.price
        })
    except Exception as e:
        current_app.logger.error(f'audit add_lab_test failed: {str(e)}', exc_info=True)

    return success_response({'id': lab_test.id, 'name': lab_test.name, 'price': lab_test.price, 'description': lab_test.description}, status=201)

@app.route('/admin/lab-tests/<int:id>')
@limiter.limit("60 per minute")
@admin_required_json
def get_lab_test(id):
    lab_test = LabTest.query.get(id)
    if not lab_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return success_response({
        'id': lab_test.id,
        'name': lab_test.name,
        'price': lab_test.price,
        'description': lab_test.description
    })

@app.route('/admin/lab-tests/<int:id>/update', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def update_lab_test(id):
    lab_test = LabTest.query.get(id)
    if not lab_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    old_data = {
        'name': lab_test.name,
        'price': lab_test.price,
        'description': lab_test.description
    }

    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    try:
        lab_test.name = name
        lab_test.price = float(price)
        lab_test.description = description
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'update_lab_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('update_lab_test', 'LabTest', lab_test.id, old_data, {
            'name': lab_test.name,
            'price': lab_test.price,
            'description': lab_test.description
        })
    except Exception as e:
        current_app.logger.error(f'audit update_lab_test failed: {str(e)}', exc_info=True)

    return success_response({'id': lab_test.id, 'name': lab_test.name, 'price': lab_test.price, 'description': lab_test.description})

@app.route('/admin/lab-tests/<int:id>/delete', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def delete_lab_test(id):
    lab_test = LabTest.query.get(id)
    if not lab_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    try:
        db.session.delete(lab_test)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'delete_lab_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('delete_lab_test', 'LabTest', lab_test.id, {
            'name': lab_test.name,
            'price': lab_test.price
        }, None)
    except Exception as e:
        current_app.logger.error(f'audit delete_lab_test failed: {str(e)}', exc_info=True)

    return success_response()

# Imaging Test CRUD
@app.route('/admin/imaging-tests/add', methods=['POST'])
@limiter.limit("10 per minute")
@admin_required_json
def add_imaging_test():
    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None
    is_active = parse_bool(request.form.get('is_active'))

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    imaging_test = ImagingTest(
        name=name,
        price=float(price),
        description=description,
        is_active=is_active
    )
    try:
        db.session.add(imaging_test)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'add_imaging_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('add_imaging_test', 'ImagingTest', imaging_test.id, None, {
            'name': imaging_test.name,
            'price': imaging_test.price,
            'is_active': imaging_test.is_active
        })
    except Exception as e:
        current_app.logger.error(f'audit add_imaging_test failed: {str(e)}', exc_info=True)

    return success_response({'id': imaging_test.id, 'name': imaging_test.name, 'price': imaging_test.price, 'description': imaging_test.description, 'is_active': imaging_test.is_active}, status=201)

@app.route('/admin/imaging-tests/<int:id>')
@limiter.limit("60 per minute")
@admin_required_json
def get_imaging_test(id):
    imaging_test = ImagingTest.query.get(id)
    if not imaging_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return success_response({
        'id': imaging_test.id,
        'name': imaging_test.name,
        'price': imaging_test.price,
        'description': imaging_test.description,
        'is_active': imaging_test.is_active
    })

@app.route('/admin/imaging-tests/<int:id>/update', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def update_imaging_test(id):
    imaging_test = ImagingTest.query.get(id)
    if not imaging_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    old_data = {
        'name': imaging_test.name,
        'price': imaging_test.price,
        'description': imaging_test.description,
        'is_active': imaging_test.is_active
    }

    name = (request.form.get('name') or '').strip()
    price_str = request.form.get('price')
    description = (request.form.get('description') or '').strip() or None
    is_active = parse_bool(request.form.get('is_active'))

    if not name:
        return bad_request('Name is required')
    price, err = parse_price(price_str)
    if err:
        return bad_request(err)

    try:
        imaging_test.name = name
        imaging_test.price = float(price)
        imaging_test.description = description
        imaging_test.is_active = is_active
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'update_imaging_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('update_imaging_test', 'ImagingTest', imaging_test.id, old_data, {
            'name': imaging_test.name,
            'price': imaging_test.price,
            'description': imaging_test.description,
            'is_active': imaging_test.is_active
        })
    except Exception as e:
        current_app.logger.error(f'audit update_imaging_test failed: {str(e)}', exc_info=True)

    return success_response({'id': imaging_test.id, 'name': imaging_test.name, 'price': imaging_test.price, 'description': imaging_test.description, 'is_active': imaging_test.is_active})

@app.route('/admin/imaging-tests/<int:id>/delete', methods=['POST'])
@limiter.limit("20 per minute")
@admin_required_json
def delete_imaging_test(id):
    imaging_test = ImagingTest.query.get(id)
    if not imaging_test:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    try:
        db.session.delete(imaging_test)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'delete_imaging_test failed: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Server error'}), 500

    try:
        log_audit('delete_imaging_test', 'ImagingTest', imaging_test.id, {
            'name': imaging_test.name,
            'price': imaging_test.price
        }, None)
    except Exception as e:
        current_app.logger.error(f'audit delete_imaging_test failed: {str(e)}', exc_info=True)

    return success_response()

@app.route('/pharmacist')
@login_required
def pharmacist_dashboard():
    try:
        if current_user.role != 'pharmacist':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('home'))
        
        # Get counts for dashboard cards
        low_stock = Drug.query.filter(Drug.remaining_quantity < 10).count()
        expiring_soon = Drug.query.filter(
            Drug.expiry_date <= date.today() + timedelta(days=30),
            Drug.expiry_date >= date.today()
        ).count()
        
        # Get recent sales (last 5)
        recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
        
        # Get pending prescriptions count
        pending_prescriptions = Prescription.query.filter_by(status='pending').count()
        
        return render_template('pharmacist/dashboard.html',
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            recent_sales=recent_sales,
            pending_prescriptions=pending_prescriptions
        )
    except Exception as e:
        current_app.logger.error(f"Error in pharmacist_dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('home'))

# Pharmacist API routes
@app.route('/pharmacist/api/dashboard-stats')
@login_required
def pharmacist_dashboard_stats():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Calculate real stats
    total_drugs = Drug.query.count()
    low_stock = Drug.query.filter(Drug.remaining_quantity < 10, Drug.remaining_quantity > 0).count()
    expiring_soon = Drug.query.filter(
        Drug.expiry_date <= date.today() + timedelta(days=30),
        Drug.expiry_date >= date.today()
    ).count()
    pending_prescriptions = Prescription.query.filter_by(status='pending').count()
    
    return jsonify({
        'success': True,
        'data': {
            'total_drugs': total_drugs,
            'low_stock': low_stock,
            'expiring_soon': expiring_soon,
            'pending_prescriptions': pending_prescriptions
        }
    })

@app.route('/pharmacist/sale/<int:sale_id>/receipt-data')
@login_required
def sale_receipt_data(sale_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    sale = Sale.query.options(
        db.joinedload(Sale.user),
        db.joinedload(Sale.items),
        db.joinedload(Sale.patient)
    ).get(sale_id)
    
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    receipt_data = {
        'sale_id': sale.id,
        'sale_number': sale.sale_number,
        'date': sale.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': sale.patient.get_decrypted_name if sale.patient else 'Walk-in Customer',
        'patient_number': sale.patient.op_number or sale.patient.ip_number if sale.patient else 'N/A',
        'pharmacist_name': sale.user.username,
        'payment_method': sale.payment_method,
        'total_amount': sale.total_amount,
        'items': []
    }
    
    for item in sale.items:
        receipt_data['items'].append({
            'name': item.drug_name,
            'specification': item.drug_specification,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    return jsonify(receipt_data)

@app.route('/pharmacist/refund/<int:refund_id>/receipt-data')
@login_required
def refund_receipt_data(refund_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    refund = Refund.query.options(
        db.joinedload(Refund.sale).joinedload(Sale.patient),
        db.joinedload(Refund.user),
        db.joinedload(Refund.items).joinedload(RefundItem.sale_item)
    ).get(refund_id)
    
    if not refund:
        return jsonify({'error': 'Refund not found'}), 404
    
    receipt_data = {
        'refund_id': refund.id,
        'refund_number': refund.refund_number,
        'sale_number': refund.sale.sale_number,
        'date': refund.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': refund.sale.patient.get_decrypted_name if refund.sale.patient else 'Walk-in Customer',
        'reason': refund.reason,
        'total_amount': refund.total_amount,
        'items': []
    }
    
    for item in refund.items:
        receipt_data['items'].append({
            'drug_name': item.sale_item.drug_name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    return jsonify(receipt_data)

# Add decrypt_data to Jinja context
@app.context_processor
def utility_processor():
    def decrypt_data(encrypted_data):
        if not encrypted_data:
            return ""
        try:
            return Config.decrypt_data_static(encrypted_data)
        except:
            return "[Decryption Error]"
    
    return dict(decrypt_data=decrypt_data)

@app.route('/pharmacist/drugs')
@login_required
def pharmacist_drugs():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get filter parameters
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    # Base query
    query = Drug.query
    
    # Apply filters
    if filter_type == 'low':
        query = query.filter(Drug.remaining_quantity < 10)
    elif filter_type == 'out':
        query = query.filter(Drug.remaining_quantity == 0)
    elif filter_type == 'expiring':
        query = query.filter(Drug.expiry_date <= date.today() + timedelta(days=30))
    
    # Apply search
    if search_query:
        query = query.filter(
            or_(
                Drug.name.ilike(f'%{search_query}%'),
                Drug.drug_number.ilike(f'%{search_query}%'),
            )
        )
    
    # Apply sorting
    if sort_by == 'name_asc':
        query = query.order_by(Drug.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Drug.name.desc())
    elif sort_by == 'stock_asc':
        query = query.order_by(Drug.remaining_quantity.asc())
    elif sort_by == 'stock_desc':
        query = query.order_by(Drug.remaining_quantity.desc())
    elif sort_by == 'expiry_asc':
        query = query.order_by(Drug.expiry_date.asc())
    elif sort_by == 'expiry_desc':
        query = query.order_by(Drug.expiry_date.desc())
    
    drugs = query.all()
    
    # Prepare response data
    drugs_data = []
    for drug in drugs:
        drugs_data.append({
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'expiry_date': drug.expiry_date.isoformat() if drug.expiry_date else None,
            'selling_price': float(drug.selling_price),
            'remaining_quantity': drug.remaining_quantity
        })
    
    return jsonify(drugs_data)

@app.route('/pharmacist/dosage')
@login_required
def pharmacist_dosage():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    dosages = DrugDosage.query.join(Drug).all()
    drugs = Drug.query.all()
    
    return render_template('pharmacist/dosage.html', dosages=dosages, drugs=drugs)

@app.route('/pharmacist/dosage/<int:dosage_id>')
@login_required
def pharmacist_get_dosage(dosage_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    dosage = DrugDosage.query.get_or_404(dosage_id)
    
    return jsonify({
        'id': dosage.id,
        'drug': {
            'id': dosage.drug.id,
            'drug_number': dosage.drug.drug_number,
            'name': dosage.drug.name
        },
        'indication': dosage.indication,
        'contraindication': dosage.contraindication,
        'interaction': dosage.interaction,
        'side_effects': dosage.side_effects,
        'dosage_peds': dosage.dosage_peds,
        'dosage_adults': dosage.dosage_adults,
        'dosage_geriatrics': dosage.dosage_geriatrics,
        'important_notes': dosage.important_notes
    })

@app.route('/pharmacist/drugs/without-dosage')
@login_required
def pharmacist_get_drugs_without_dosage():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drugs = Drug.query.filter(~Drug.dosage.any()).all()
    
    return jsonify([{
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name
    } for drug in drugs])

@app.route('/pharmacist/drugs/<int:drug_id>/dosage')
@login_required
def pharmacist_get_drug_dosage(drug_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    dosage = DrugDosage.query.filter_by(drug_id=drug.id).first()
    
    return jsonify({
        'drug': {
            'id': drug.id,
            'name': drug.name,
            'drug_number': drug.drug_number
        },
        'dosage': {
            'indication': dosage.indication if dosage else None,
            'contraindication': dosage.contraindication if dosage else None,
            'interaction': dosage.interaction if dosage else None,
            'side_effects': dosage.side_effects if dosage else None,
            'dosage_peds': dosage.dosage_peds if dosage else None,
            'dosage_adults': dosage.dosage_adults if dosage else None,
            'dosage_geriatrics': dosage.dosage_geriatrics if dosage else None,
            'important_notes': dosage.important_notes if dosage else None
        } if dosage else None
    })

@app.route('/pharmacist/inventory')
@login_required
def pharmacist_inventory():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    try:
        drugs = Drug.query.options(db.joinedload(Drug.dosage)).order_by(Drug.name).all()
        
        total_drugs = Drug.query.count()
        low_stock = Drug.query.filter(Drug.remaining_quantity < 10, Drug.remaining_quantity > 0).count()
        expiring_soon = Drug.query.filter(
            Drug.expiry_date <= date.today() + timedelta(days=30),
            Drug.expiry_date >= date.today()
        ).count()
        out_of_stock = Drug.query.filter(Drug.remaining_quantity == 0).count()
        
        return render_template('pharmacist/inventory.html',
            drugs=drugs,
            total_drugs=total_drugs,
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            out_of_stock=out_of_stock
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading inventory: {str(e)}")
        flash('An error occurred while loading inventory', 'danger')
        return redirect(url_for('pharmacist_dashboard'))


@app.route('/pharmacist/controlled-inventory')
@login_required
def pharmacist_controlled_inventory():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    try:
        controlled_drugs = ControlledDrug.query.order_by(ControlledDrug.name).all()
        return render_template('pharmacist/controlled_inventory.html', controlled_drugs=controlled_drugs)
    except Exception as e:
        current_app.logger.error(f"Error loading controlled inventory: {str(e)}")
        flash('An error occurred while loading controlled inventory', 'danger')
        return redirect(url_for('pharmacist_dashboard'))


@app.route('/pharmacist/api/controlled-prescriptions')
@login_required
def pharmacist_controlled_prescriptions_list():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        prescriptions = ControlledPrescription.query.filter_by(status='pending').options(
            db.joinedload(ControlledPrescription.patient),
            db.joinedload(ControlledPrescription.doctor),
            db.joinedload(ControlledPrescription.items).joinedload(ControlledPrescriptionItem.controlled_drug)
        ).order_by(ControlledPrescription.created_at.asc()).all()

        result = []
        for p in prescriptions:
            patient_name = 'Unknown Patient'
            try:
                if p.patient and hasattr(p.patient, 'get_decrypted_name'):
                    patient_name = p.patient.get_decrypted_name()
                elif p.patient:
                    patient_name = str(p.patient)
            except Exception:
                patient_name = 'Error loading patient'

            result.append({
                'id': p.id,
                'patient_name': patient_name,
                'patient_number': p.patient.op_number or p.patient.ip_number if p.patient else 'N/A',
                'doctor_name': p.doctor.username if p.doctor else 'Unknown Doctor',
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else 'Unknown Date',
                'items_count': len(p.items) if p.items else 0,
                'status': p.status,
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching controlled prescriptions: {str(e)}")
        return jsonify({'error': 'Failed to fetch controlled prescriptions'}), 500


@app.route('/pharmacist/api/controlled-prescription/<int:prescription_id>')
@login_required
def pharmacist_controlled_prescription_details(prescription_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        p = db.session.query(ControlledPrescription).options(
            db.joinedload(ControlledPrescription.items).joinedload(ControlledPrescriptionItem.controlled_drug),
            db.joinedload(ControlledPrescription.patient),
            db.joinedload(ControlledPrescription.doctor),
        ).filter(ControlledPrescription.id == prescription_id).first()

        if not p:
            return jsonify({'error': 'Controlled prescription not found'}), 404

        patient_name = 'Unknown Patient'
        try:
            if p.patient and hasattr(p.patient, 'get_decrypted_name'):
                patient_name = p.patient.get_decrypted_name()
            elif p.patient:
                patient_name = str(p.patient)
        except Exception:
            patient_name = 'Error loading patient'

        items = []
        for item in p.items:
            cd = item.controlled_drug
            items.append({
                'id': item.id,
                'controlled_drug_id': item.controlled_drug_id,
                'controlled_drug_name': cd.name if cd else 'Unknown Drug',
                'controlled_drug_number': cd.controlled_drug_number if cd else 'N/A',
                'quantity': item.quantity,
                'dosage': item.dosage or '',
                'frequency': item.frequency or '',
                'duration': item.duration or '',
                'notes': item.notes or '',
                'remaining_quantity': cd.remaining_quantity if cd else 0,
            })

        return jsonify({
            'id': p.id,
            'patient_id': p.patient_id,
            'patient_name': patient_name,
            'patient_number': p.patient.op_number or p.patient.ip_number if p.patient else 'N/A',
            'doctor_name': p.doctor.username if p.doctor else 'Unknown Doctor',
            'notes': p.notes or '',
            'status': p.status,
            'created_at': p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else 'Unknown Date',
            'items': items,
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching controlled prescription details: {str(e)}")
        return jsonify({'error': 'Failed to fetch controlled prescription details'}), 500


@app.route('/pharmacist/controlled/dispense', methods=['POST'])
@login_required
def pharmacist_controlled_dispense():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.get_json() or {}
        prescription_id = data.get('controlled_prescription_id')
        payment_method = data.get('payment_method', 'cash')

        if not prescription_id:
            return jsonify({'error': 'Controlled prescription ID is required'}), 400

        p = db.session.query(ControlledPrescription).options(
            db.joinedload(ControlledPrescription.items).joinedload(ControlledPrescriptionItem.controlled_drug),
            db.joinedload(ControlledPrescription.patient),
        ).filter(ControlledPrescription.id == prescription_id).first()

        if not p:
            return jsonify({'error': 'Controlled prescription not found'}), 404
        if p.status != 'pending':
            return jsonify({'error': 'Controlled prescription has already been processed'}), 400

        # Verify stock
        for item in p.items:
            if not item.controlled_drug:
                return jsonify({'error': 'Controlled drug missing on prescription item'}), 400
            if item.controlled_drug.remaining_quantity < item.quantity:
                return jsonify({
                    'error': f'Insufficient stock for {item.controlled_drug.name}',
                    'details': f'Requested: {item.quantity}, Available: {item.controlled_drug.remaining_quantity}',
                    'controlled_drug_id': item.controlled_drug.id
                }), 400

        total_amount = sum(float(item.controlled_drug.selling_price) * int(item.quantity) for item in p.items)
        sale_number = generate_controlled_sale_number()

        sale = ControlledSale(
            sale_number=sale_number,
            patient_id=p.patient_id,
            user_id=current_user.id,
            pharmacist_name=f"{current_user.username}",
            total_amount=total_amount,
            payment_method=payment_method,
            status='completed',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(sale)
        db.session.flush()

        for idx, item in enumerate(p.items):
            cd = item.controlled_drug
            unit_price = float(cd.selling_price)
            qty = int(item.quantity)
            db.session.add(ControlledSaleItem(
                sale_id=sale.id,
                controlled_drug_id=cd.id,
                controlled_drug_name=cd.name,
                controlled_drug_specification=cd.specification,
                individual_sale_number=f"{sale_number}-{idx+1:02d}",
                description=f"Controlled prescription: {cd.name}",
                prescription_source='internal',
                prescription_sheet_path=None,
                quantity=qty,
                unit_price=unit_price,
                total_price=unit_price * qty,
                created_at=datetime.now(timezone.utc)
            ))

            cd.sold_quantity = (cd.sold_quantity or 0) + qty
            db.session.add(cd)

            item.status = 'dispensed'

        p.status = 'dispensed'
        db.session.commit()

        try:
            log_audit('dispense_controlled_prescription', 'ControlledPrescription', p.id, None, {
                'controlled_sale_id': sale.id,
                'sale_number': sale.sale_number,
                'total_amount': total_amount,
                'payment_method': payment_method,
            })
        except Exception:
            pass

        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount,
            'message': 'Controlled prescription dispensed successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dispensing controlled prescription: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to dispense controlled prescription', 'details': str(e)}), 500


@app.route('/pharmacist/controlled/external-sale', methods=['POST'])
@login_required
def pharmacist_controlled_external_sale():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    try:
        controlled_drug_id = request.form.get('controlled_drug_id', type=int)
        quantity = request.form.get('quantity', type=int)
        patient_id = request.form.get('patient_id', type=int)
        payment_method = request.form.get('payment_method', 'cash')
        sheet = request.files.get('prescription_sheet')

        if not controlled_drug_id or not quantity or quantity <= 0:
            flash('Please select a controlled drug and valid quantity.', 'danger')
            return redirect(url_for('pharmacist_controlled_inventory'))

        if not sheet or not getattr(sheet, 'filename', None):
            flash('Prescription sheet is required for external/OTC controlled sales.', 'danger')
            return redirect(url_for('pharmacist_controlled_inventory'))

        cdrug = db.session.get(ControlledDrug, controlled_drug_id)
        if not cdrug:
            flash('Controlled drug not found.', 'danger')
            return redirect(url_for('pharmacist_controlled_inventory'))

        if cdrug.remaining_quantity < quantity:
            flash(f'Insufficient stock for {cdrug.name}. Available: {cdrug.remaining_quantity}', 'danger')
            return redirect(url_for('pharmacist_controlled_inventory'))

        if patient_id:
            patient = db.session.get(Patient, patient_id)
            if not patient:
                flash('Selected patient not found.', 'danger')
                return redirect(url_for('pharmacist_controlled_inventory'))

        sheet_path = _save_prescription_sheet(sheet)
        sale_number = generate_controlled_sale_number()
        unit_price = float(cdrug.selling_price)
        total_amount = unit_price * quantity

        sale = ControlledSale(
            sale_number=sale_number,
            patient_id=patient_id if patient_id else None,
            user_id=current_user.id,
            pharmacist_name=f"{current_user.username}",
            total_amount=total_amount,
            payment_method=payment_method,
            status='completed',
            notes='External controlled sale',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(sale)
        db.session.flush()

        db.session.add(ControlledSaleItem(
            sale_id=sale.id,
            controlled_drug_id=cdrug.id,
            controlled_drug_name=cdrug.name,
            controlled_drug_specification=cdrug.specification,
            individual_sale_number=f"{sale_number}-01",
            description=f"External controlled sale: {cdrug.name}",
            prescription_source='external',
            prescription_sheet_path=sheet_path,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_amount,
            created_at=datetime.now(timezone.utc)
        ))

        cdrug.sold_quantity = (cdrug.sold_quantity or 0) + quantity
        db.session.add(cdrug)
        db.session.commit()

        try:
            log_audit('external_controlled_sale', 'ControlledSale', sale.id, None, {
                'sale_number': sale.sale_number,
                'patient_id': sale.patient_id,
                'controlled_drug_id': cdrug.id,
                'quantity': quantity,
                'total_amount': total_amount,
                'prescription_sheet_path': sheet_path,
            })
        except Exception:
            pass

        flash('External controlled sale recorded successfully.', 'success')
        return redirect(url_for('pharmacist_controlled_inventory'))

    except ValueError as ve:
        db.session.rollback()
        flash(str(ve), 'danger')
        return redirect(url_for('pharmacist_controlled_inventory'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing external controlled sale: {str(e)}", exc_info=True)
        flash('Failed to process external controlled sale.', 'danger')
        return redirect(url_for('pharmacist_controlled_inventory'))
    
@app.route('/pharmacist/drugs/export')
@login_required
def export_drugs():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    query = Drug.query
    
    if filter_type == 'low':
        query = query.filter(Drug.remaining_quantity < 10)
    elif filter_type == 'out':
        query = query.filter(Drug.remaining_quantity == 0)
    elif filter_type == 'expiring':
        query = query.filter(Drug.expiry_date <= date.today() + timedelta(days=30))
    
    if search_query:
        query = query.filter(
            or_(
                Drug.name.ilike(f'%{search_query}%'),
                Drug.drug_number.ilike(f'%{search_query}%'),
            )
        )
    
    if sort_by == 'name_asc':
        query = query.order_by(Drug.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Drug.name.desc())
    elif sort_by == 'stock_asc':
        query = query.order_by(Drug.remaining_quantity.asc())
    elif sort_by == 'stock_desc':
        query = query.order_by(Drug.remaining_quantity.desc())
    elif sort_by == 'expiry_asc':
        query = query.order_by(Drug.expiry_date.asc())
    elif sort_by == 'expiry_desc':
        query = query.order_by(Drug.expiry_date.desc())
    
    drugs = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'Drug Number', 'Name', 'Expiry Date', 'Selling Price', 'Stock'
    ])
    
    for drug in drugs:
        if drug.remaining_quantity == 0:
            status = 'Out of Stock'
        elif drug.remaining_quantity < 10:
            status = 'Low Stock'
        else:
            status = 'In Stock'
        
        if drug.expiry_date and (drug.expiry_date <= date.today() + timedelta(days=30)):
            status += ' (Expiring Soon)'
        
        writer.writerow([
            drug.drug_number,
            drug.name,
            drug.expiry_date.strftime('%Y-%m-%d') if drug.expiry_date else '',
            f"Ksh {drug.selling_price:.2f}",
            drug.remaining_quantity,
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=drug_inventory.csv'
    response.headers['Content-type'] = 'text/csv'
    
    return response

@app.route('/pharmacist/sales')
@login_required
def pharmacist_sales():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    sales = Sale.query.order_by(Sale.created_at.desc()).limit(50).all()
    return render_template('pharmacist/sales.html', sales=sales)


@app.route('/pharmacist/cart_sale', methods=['POST'])
@login_required
def process__cart_sale():
    if current_user.role != 'pharmacist':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400
        
        # Validate required fields
        if 'items' not in data:
            return jsonify({'success': False, 'error': 'Missing items field'}), 400
        
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        
        if not items:
            return jsonify({'success': False, 'error': 'No items in cart'}), 400
        
        # Validate each item
        for i, item in enumerate(items):
            if 'drug_id' not in item:
                return jsonify({'success': False, 'error': f'Missing drug_id in item {i+1}'}), 400
            if 'quantity' not in item:
                return jsonify({'success': False, 'error': f'Missing quantity in item {i+1}'}), 400
            if 'unit_price' not in item:
                return jsonify({'success': False, 'error': f'Missing unit_price in item {i+1}'}), 400
        
        # Generate sale numbers
        sale_number = f"SALE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        
        # Calculate total amount
        total_amount = sum(float(item.get('unit_price', 0)) * int(item.get('quantity', 0)) for item in items)
        
        # Create sale record
        sale = Sale(
            sale_number=sale_number,
            patient_id=None,  # Walk-in sale
            user_id=current_user.id,
            pharmacist_name=f"{current_user.username}",
            total_amount=total_amount,
            payment_method=payment_method,
            status='completed',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(sale)
        db.session.flush()
        
        # Process each item
        for item_index, item_data in enumerate(items):
            drug_id = item_data.get('drug_id')
            quantity = int(item_data.get('quantity', 1))
            unit_price = float(item_data.get('unit_price', 0))
            
            if not drug_id or quantity <= 0:
                continue
            
            # Get drug from database
            drug = db.session.get(Drug, drug_id)
            if not drug:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Drug with ID {drug_id} not found'
                }), 400
            
            # Check stock availability
            if drug.remaining_quantity < quantity:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Insufficient stock for {drug.name}',
                    'available': drug.remaining_quantity,
                    'requested': quantity,
                    'drug_id': drug.id
                }), 400
            
            # Create sale item
            sale_item = SaleItem(
                sale_id=sale.id,
                drug_id=drug_id,
                drug_name=drug.name,
                drug_specification=drug.specification,
                individual_sale_number=f"{sale_number}-{item_index+1:02d}",
                description=f"Sale of {drug.name}",
                quantity=quantity,
                unit_price=unit_price,
                total_price=unit_price * quantity,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(sale_item)
            
            # Update drug stock
            drug.sold_quantity += quantity
            db.session.add(drug)
        
        # Create transaction record
        transaction = Transaction(
            transaction_number=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}",
            transaction_type='sale',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=sale.id,
            notes=f"Sale #{sale.sale_number}",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(transaction)
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': sale.total_amount,
            'message': 'Sale processed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing sale: {str(e)}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': 'Failed to process sale',
            'details': str(e)
        }), 500
        
@app.route('/pharmacist/sale/<int:sale_id>/receipt')
@login_required
def generate_receipt(sale_id):
    if current_user.role != 'pharmacist':
        abort(403)
    
    sale = db.session.query(Sale).options(
        db.joinedload(Sale.user),
        db.joinedload(Sale.items).joinedload(SaleItem.drug),
        db.joinedload(Sale.patient)
    ).where(Sale.id == sale_id).first()
    
    if not sale:
        abort(404)
    
    related_sales = []
    if sale.bulk_sale_number:
        related_sales = db.session.query(Sale).filter(
            Sale.bulk_sale_number == sale.bulk_sale_number,
            Sale.id != sale.id
        ).options(
            db.joinedload(Sale.items).joinedload(SaleItem.drug)
        ).all()
    
    return render_template('pharmacist/receipt.html', 
                         sale=sale,
                         related_sales=related_sales,
                         now=datetime.now())

@app.route('/pharmacist/refunds')
@login_required
def pharmacist_refunds():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    return render_template('pharmacist/refunds.html')

@app.route('/pharmacist/sales/search', methods=['GET'])
@login_required
def search_sale():
    sale_number = request.args.get('sale_number')
    
    sale = Sale.query.filter((Sale.sale_number == sale_number) | 
                           (Sale.bulk_sale_number == sale_number)).first()
    
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    items = []
    for item in sale.items:
        items.append({
            'id': item.id,
            'individual_sale_number': item.individual_sale_number,
            'drug_id': item.drug_id,
            'drug_name': item.drug.name,
            'quantity_sold': item.quantity,
            'quantity_remaining': item.quantity - sum(
                ri.quantity for ri in item.refunds
            ) if item.refunds else item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    return jsonify({
        'sale_number': sale.sale_number,
        'bulk_sale_number': sale.bulk_sale_number,
        'is_bulk': bool(sale.bulk_sale_number),
        'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': sale.patient.name if sale.patient else 'Walk-in',
        'total_amount': sale.total_amount,
        'items': items
    })

@app.route('/pharmacist/refund/search', methods=['GET'])
@login_required
def search_sale_for_refund():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    sale_number = request.args.get('sale_number')
    if not sale_number:
        return jsonify({'error': 'Sale number is required'}), 400
    
    sale = db.session.query(Sale).filter(
        (Sale.sale_number == sale_number) | 
        (Sale.bulk_sale_number == sale_number)
    ).first()
    
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    items = []
    for item in sale.items:
        if item.drug_id:
            refunded_qty = sum(ri.quantity for ri in item.refund_items) if item.refund_items else 0
            remaining_qty = item.quantity - refunded_qty
            
            if remaining_qty > 0:
                items.append({
                    'id': item.id,
                    'sale_item_id': item.id,
                    'drug_id': item.drug_id,
                    'drug_name': item.drug_name,
                    'unit_price': item.unit_price,
                    'quantity_sold': item.quantity,
                    'quantity_refunded': refunded_qty,
                    'quantity_remaining': remaining_qty,
                    'total_price': item.total_price
                })
    
    return jsonify({
        'sale_id': sale.id,
        'sale_number': sale.sale_number,
        'bulk_sale_number': sale.bulk_sale_number,
        'is_bulk': bool(sale.bulk_sale_number),
        'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': sale.patient.get_decrypted_name if sale.patient else 'Walk-in Customer',
        'total_amount': sale.total_amount,
        'items': items
    })

@app.route('/pharmacist/refund', methods=['POST'])
@login_required
def process_refund():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    sale_id = data.get('sale_id')
    items = data.get('items', [])
    reason = data.get('reason', '')
    
    if not sale_id:
        return jsonify({'error': 'Sale ID is required'}), 400
    
    if not items:
        return jsonify({'error': 'No items selected for refund'}), 400
    
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    try:
        refund = Refund(
            refund_number=generate_refund_number(),  # This function needs to be defined
            sale_id=sale.id,
            user_id=current_user.id,
            total_amount=0,
            status='completed',
            reason=reason
        )
        db.session.add(refund)
        db.session.flush()
        
        total_amount = 0
        
        for item_data in items:
            sale_item_id = item_data.get('sale_item_id')
            quantity = int(item_data.get('quantity'))
            
            if quantity <= 0:
                continue
            
            sale_item = db.session.get(SaleItem, sale_item_id)
            if not sale_item or sale_item.sale_id != sale.id:
                continue
            
            refunded_qty = sum(ri.quantity for ri in sale_item.refund_items) if sale_item.refund_items else 0
            max_refundable = sale_item.quantity - refunded_qty
            
            if quantity > max_refundable:
                return jsonify({
                    'error': f'Cannot refund more than {max_refundable} for {sale_item.drug_name}'
                }), 400
            
            if sale_item.drug_id:
                drug = db.session.get(Drug, sale_item.drug_id)
                if drug:
                    drug.sold_quantity -= quantity
                    drug.stocked_quantity += quantity
            
            item_total = sale_item.unit_price * quantity
            refund_item = RefundItem(
                refund_id=refund.id,
                sale_item_id=sale_item.id,
                quantity=quantity,
                unit_price=sale_item.unit_price,
                total_price=item_total
            )
            db.session.add(refund_item)
            
            total_amount += item_total
        
        refund.total_amount = total_amount
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='refund',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=refund.id,
            notes=f'Refund for sale {sale.sale_number}'
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'refund_id': refund.id,
            'refund_number': refund.refund_number,
            'total_amount': total_amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def generate_refund_number():
    return f"REF-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

@app.route('/pharmacist/refund/<int:refund_id>/receipt')
@login_required
def refund_receipt(refund_id):
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    refund = db.session.query(Refund).options(
        db.joinedload(Refund.sale).joinedload(Sale.patient),
        db.joinedload(Refund.user),
        db.joinedload(Refund.items).joinedload(RefundItem.sale_item)
    ).get(refund_id)
    
    if not refund:
        flash('Refund not found', 'danger')
        return redirect(url_for('pharmacist_refunds'))
    
    return render_template('pharmacist/refund_receipt.html', refund=refund)

    
# Pharmacist Prescription Routes
@app.route('/pharmacist/prescriptions')
@login_required
def patient_prescriptions():
    """Get all pending prescriptions for pharmacist"""
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get pending prescriptions with related data
        prescriptions = Prescription.query.filter_by(status='pending').options(
            db.joinedload(Prescription.patient),
            db.joinedload(Prescription.doctor),
            db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug)
        ).order_by(Prescription.created_at.asc()).all()
        
        prescription_data = []
        for prescription in prescriptions:
            # Safely get patient name - handle the method properly
            patient_name = ""
            try:
                if hasattr(prescription.patient, 'get_decrypted_name'):
                    # Call the method to get the actual value
                    patient_name = prescription.patient.get_decrypted_name()
                else:
                    patient_name = str(prescription.patient) if prescription.patient else "Unknown Patient"
            except Exception as e:
                current_app.logger.error(f"Error getting patient name: {str(e)}")
                patient_name = "Error loading patient"
            
            prescription_data.append({
                'id': prescription.id,
                'patient_name': patient_name,
                'patient_number': prescription.patient.op_number or prescription.patient.ip_number if prescription.patient else "N/A",
                'doctor_name': prescription.doctor.username if prescription.doctor else "Unknown Doctor",
                'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M') if prescription.created_at else "Unknown Date",
                'items_count': len(prescription.items) if prescription.items else 0,
                'status': prescription.status
            })
        
        return jsonify(prescription_data)
    
    except Exception as e:
        current_app.logger.error(f"Error fetching prescriptions: {str(e)}")
        return jsonify({'error': 'Failed to fetch prescriptions'}), 500
    
    
@app.route('/pharmacist/prescriptions/check-new')
@login_required
def check_new_prescriptions():
    """Check if there are new pending prescriptions"""
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get the count of pending prescriptions
        pending_count = db.session.query(Prescription).filter_by(status='pending').count()
        
        # You could also track the last checked time for each pharmacist
        # For simplicity, we'll just return if there are any pending prescriptions
        
        return jsonify({
            'success': True,
            'has_new_prescriptions': pending_count > 0,
            'pending_count': pending_count
        })
    
    except Exception as e:
        current_app.logger.error(f"Error checking new prescriptions: {str(e)}")
        return jsonify({'error': 'Failed to check prescriptions'}), 500


@app.route('/pharmacist/prescription/<int:id>/delete', methods=['POST'])
@login_required
def delete_prescription(id):
    """Allow pharmacist or admin to delete a prescription (only if not dispensed)."""
    if current_user.role not in ('pharmacist', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    prescription = Prescription.query.get_or_404(id)
    try:
        if prescription.status == 'dispensed':
            return jsonify({'success': False, 'error': 'Cannot remove a dispensed prescription'}), 400

        # Delete associated items first
        PrescriptionItem.query.filter_by(prescription_id=prescription.id).delete()

        # Then delete the prescription
        db.session.delete(prescription)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Prescription removed'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting prescription {id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to remove prescription'}), 500

@app.route('/doctor/complete_prescription', methods=['POST'])
@login_required
def doctor_complete_prescription():
    """Doctor completes a prescription - this should trigger pharmacist notification"""
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        prescription_data = data.get('prescription_data')
        
        if not patient_id or not prescription_data:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        # Create prescription record
        prescription = Prescription(
            patient_id=patient_id,
            doctor_id=current_user.id,
            notes=prescription_data.get('notes', ''),
            status='pending'  # Set to pending for pharmacist to dispense
        )
        db.session.add(prescription)
        db.session.flush()  # Get prescription ID
        
        # Add prescription items
        for item in prescription_data.get('items', []):
            prescription_item = PrescriptionItem(
                prescription_id=prescription.id,
                drug_id=item['drug_id'],
                quantity=item['quantity'],
                dosage=item.get('dosage', ''),
                frequency=item.get('frequency', ''),
                duration=item.get('duration', ''),
                notes=item.get('notes', ''),
                status='pending'
            )
            db.session.add(prescription_item)
        
        db.session.commit()
        
        # Log the prescription creation
        log_audit(
            'create_prescription',
            'Prescription',
            prescription.id,
            None,
            {
                'patient_id': patient_id,
                'doctor_id': current_user.id,
                'items_count': len(prescription_data.get('items', []))
            }
        )
        
        return jsonify({
            'success': True,
            'prescription_id': prescription.id,
            'message': 'Prescription completed successfully and sent to pharmacy'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error completing prescription: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/pharmacist/prescription/<int:prescription_id>')
@login_required
def get_prescription_details(prescription_id):
    """Get detailed information about a specific prescription"""
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # FIXED: Use db.session.get() instead of Query.get()
        prescription = db.session.get(Prescription, prescription_id)
        
        if not prescription:
            return jsonify({'error': 'Prescription not found'}), 404
        
        items_data = []
        for item in prescription.items:
            items_data.append({
                'id': item.id,
                'drug_id': item.drug_id,
                'drug_name': item.drug.name if item.drug else "Unknown Drug",
                'drug_number': item.drug.drug_number if item.drug else "N/A",
                'dosage': item.dosage or "",
                'frequency': item.frequency or "",
                'duration': item.duration or "",
                'quantity': item.quantity,
                'notes': item.notes or "",
                'drug': {
                    'id': item.drug.id if item.drug else None,
                    'name': item.drug.name if item.drug else "Unknown Drug",
                    'remaining_quantity': item.drug.remaining_quantity if item.drug else 0
                } if item.drug else None
            })
        
        # Safely get patient name
        patient_name = ""
        try:
            if hasattr(prescription.patient, 'get_decrypted_name'):
                patient_name = prescription.patient.get_decrypted_name()
            else:
                patient_name = str(prescription.patient) if prescription.patient else "Unknown Patient"
        except Exception as e:
            current_app.logger.error(f"Error getting patient name: {str(e)}")
            patient_name = "Error loading patient"
        
        return jsonify({
            'id': prescription.id,
            'patient_id': prescription.patient_id,
            'patient_name': patient_name,
            'patient_number': prescription.patient.op_number or prescription.patient.ip_number if prescription.patient else "N/A",
            'doctor_id': prescription.doctor_id,
            'doctor_name': prescription.doctor.username if prescription.doctor else "Unknown Doctor",
            'notes': prescription.notes or "",
            'status': prescription.status,
            'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M') if prescription.created_at else "Unknown Date",
            'items': items_data
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching prescription details: {str(e)}")
        return jsonify({'error': 'Failed to fetch prescription details'}), 500


@app.route('/pharmacist/dispense', methods=['POST'])
@login_required
def pharmacist_dispense():
    """Dispense a prescription and update inventory"""
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        prescription_id = data.get('prescription_id')
        payment_method = data.get('payment_method', 'cash')
        
        if not prescription_id:
            return jsonify({'error': 'Prescription ID is required'}), 400
        
        # Get prescription with related data
        prescription = db.session.query(Prescription).options(
            db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug),
            db.joinedload(Prescription.patient)
        ).get(prescription_id)
        
        if not prescription:
            return jsonify({'error': 'Prescription not found'}), 404
        
        if prescription.status != 'pending':
            return jsonify({'error': 'Prescription has already been processed'}), 400
        
        # Verify all items are available
        for item in prescription.items:
            if item.drug.remaining_quantity < item.quantity:
                return jsonify({
                    'error': f'Insufficient stock for {item.drug.name}',
                    'details': f'Requested: {item.quantity}, Available: {item.drug.remaining_quantity}',
                    'drug_id': item.drug.id
                }), 400
        
        # Calculate total amount
        total_amount = sum(item.drug.selling_price * item.quantity for item in prescription.items)
        
        # Create sale record
        sale = Sale(
            sale_number=generate_sale_number(),
            patient_id=prescription.patient_id,
            user_id=current_user.id,
            total_amount=total_amount,
            payment_method=payment_method,
            status='completed'
        )
        db.session.add(sale)
        db.session.flush()  # Get sale ID
        
        # Create sale items and update drug inventory
        for item in prescription.items:
            sale_item = SaleItem(
                sale_id=sale.id,
                drug_id=item.drug_id,
                drug_name=item.drug.name,
                drug_specification=item.drug.specification,
                description=f"Prescription: {item.drug.name}",
                quantity=item.quantity,
                unit_price=item.drug.selling_price,
                total_price=item.drug.selling_price * item.quantity
            )
            db.session.add(sale_item)
            
            # Update drug inventory
            item.drug.sold_quantity += item.quantity
        
        # Update prescription status
        prescription.status = 'dispensed'
        
        # Create transaction record
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='sale',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=sale.id,
            notes=f"Prescription dispense: {prescription.id}"
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        # Log the action
        log_audit(
            'dispense_prescription',
            'Prescription',
            prescription.id,
            None,
            {
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'total_amount': total_amount,
                'payment_method': payment_method
            }
        )
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount,
            'message': 'Prescription dispensed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dispensing prescription: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Failed to process prescription',
            'details': str(e)
        }), 500
@app.route('/pharmacist/sale/<int:sale_id>/receipt')
@login_required
def get_sale_receipt(sale_id):
    """Get receipt for a completed sale"""
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        sale = Sale.query.options(
            db.joinedload(Sale.patient),
            db.joinedload(Sale.items),
            db.joinedload(Sale.user)
        ).get(sale_id)
        
        if not sale:
            return jsonify({'error': 'Sale not found'}), 404
        
        receipt_data = {
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'date': sale.created_at.strftime('%Y-%m-%d %H:%M'),
            'patient_name': sale.patient.get_decrypted_name if sale.patient else 'Walk-in Customer',
            'patient_number': sale.patient.op_number or sale.patient.ip_number if sale.patient else 'N/A',
            'pharmacist_name': sale.user.username,
            'payment_method': sale.payment_method,
            'total_amount': sale.total_amount,
            'items': []
        }
        
        for item in sale.items:
            receipt_data['items'].append({
                'name': item.drug_name,
                'specification': item.drug_specification,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            })
        
        return jsonify(receipt_data)
    
    except Exception as e:
        current_app.logger.error(f"Error generating receipt: {str(e)}")
        
        return jsonify({'error': 'Failed to generate receipt'}), 500

   
# Doctor Routes
@app.route('/doctor')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Get counts for the stats cards
    active_patients_count = Patient.query.filter_by(status='active').count()
    today_patients = Patient.query.filter(
        func.date(Sale.created_at) == date.today()
    ).count()
    completed_patients_count = Patient.query.filter_by(status='completed').count()
    
    # Get actual patient lists for the tables
    active_patients = Patient.query.filter_by(status='active').order_by(Patient.updated_at.desc()).limit(50).all()
    completed_patients = Patient.query.filter_by(status='completed').order_by(Patient.updated_at.desc()).limit(50).all()
    
    return render_template('doctor/dashboard.html',
        active_patients_count=active_patients_count,
        today_patients=today_patients,
        completed_patients_count=completed_patients_count,
        active_patients=active_patients,
        completed_patients=completed_patients,
        recent_activities=[]  # Empty list until audit is properly set up
    )

        
@app.route('/generate_patient_number')
@login_required
def get_patient_number():
    patient_type = request.args.get('type')
    if patient_type not in ['OP', 'IP']:
        return jsonify({'error': 'Invalid patient type'}), 400
    
    number = generate_patient_number(patient_type)
    return jsonify({'number': number})

def generate_patient_number(patient_type):
    """Generate patient number in format OP MNC001 or IP MNC001"""
    prefix = 'OP' if patient_type == 'OP' else 'IP'
    last_patient = Patient.query.filter(
        Patient.op_number.like(f'{prefix} MNC%') if patient_type == 'OP' else Patient.ip_number.like(f'{prefix} MNC%')
    ).order_by(
        Patient.op_number.desc() if patient_type == 'OP' else Patient.ip_number.desc()
    ).first()
    
    if last_patient:
        last_number_str = (last_patient.op_number if patient_type == 'OP' else last_patient.ip_number).split('MNC')[-1]
        last_number = int(last_number_str)
        new_number = f"{prefix} MNC{str(last_number + 1).zfill(3)}"
    else:
        new_number = f"{prefix} MNC001"
    
    return new_number

@app.route('/doctor/patients', methods=['GET'])
@login_required
def doctor_patients():
    if current_user.role != 'doctor':
        flash('Unauthorized', 'danger')
        return redirect(url_for('home'))

    active_patients = Patient.query.filter_by(status='active').order_by(Patient.created_at.desc()).all()
    completed_patients = Patient.query.filter_by(status='completed').order_by(Patient.updated_at.desc()).all()

    return render_template(
        'doctor/patients.html',
        active_patients=active_patients,
        completed_patients=completed_patients
    )

@app.route('/doctor/patient/<int:patient_id>/summary', methods=['GET', 'POST'])
@login_required
def patient_summary(patient_id):
    if current_user.role not in ['doctor', 'admin']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_manual':
            try:
                summary_text = request.form.get('summary_text')
                if not summary_text:
                    return jsonify({'success': False, 'error': 'Summary text is required'}), 400
                
                summary = PatientSummary(
                    patient_id=patient.id,
                    summary_text=summary_text,
                    summary_type='manual'
                )
                db.session.add(summary)
                db.session.commit()
                
                return jsonify({'success': True, 'message': 'Summary saved successfully'})
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        elif action == 'generate_ai':
            try:
                # Collect all patient data for summary generation
                review_systems = db.session.execute(
                    db.select(PatientReviewSystem).filter_by(patient_id=patient.id)
                ).scalar()
                
                history = db.session.execute(
                    db.select(PatientHistory).filter_by(patient_id=patient.id)
                ).scalar()
                
                examination = db.session.execute(
                    db.select(PatientExamination).filter_by(patient_id=patient.id)
                ).scalar()
                
                diagnosis = db.session.execute(
                    db.select(PatientDiagnosis).filter_by(patient_id=patient.id)
                ).scalar()

                patient_data = {
                    'name': patient.get_decrypted_name,
                    'age': patient.age,
                    'gender': patient.gender,
                    'address': patient.get_decrypted_address or '',
                    'occupation': patient.get_decrypted_occupation or '',
                    'religion': patient.religion or '',
                    'chief_complaint': patient.chief_complaint or '',
                    'history_present_illness': patient.history_present_illness or '',
                    'review_systems': {
                        'cns': review_systems.cns if review_systems else '',
                        'cvs': review_systems.cvs if review_systems else '',
                        'rs': review_systems.rs if review_systems else '',
                        'git': review_systems.git if review_systems else '',
                        'gut': review_systems.gut if review_systems else '',
                        'skin': review_systems.skin if review_systems else '',
                        'msk': review_systems.msk if review_systems else ''
                    } if review_systems else {},
                    'social_history': history.social_history if history else '',
                    'medical_history': history.medical_history if history else '',
                    'surgical_history': history.surgical_history if history else '',
                    'family_history': history.family_history if history else '',
                    'allergies': history.allergies if history else '',
                    'medications': history.medications if history else '',
                    'examination': {
                        'general_appearance': examination.general_appearance if examination else '',
                        'vitals': {
                            'temperature': examination.temperature if examination else None,
                            'pulse': examination.pulse if examination else None,
                            'bp': f"{examination.bp_systolic}/{examination.bp_diastolic}" if examination and examination.bp_systolic and examination.bp_diastolic else None,
                            'resp_rate': examination.resp_rate if examination else None,
                            'spo2': examination.spo2 if examination else None
                        },
                        'systems': {
                            'cvs': examination.cvs_exam if examination else '',
                            'respiratory': examination.resp_exam if examination else '',
                            'abdominal': examination.abdo_exam if examination else '',
                            'cns': examination.cns_exam if examination else ''
                        }
                    } if examination else {},
                    'working_diagnosis': diagnosis.working_diagnosis if diagnosis else ''
                }
                
                summary_text = AIService.generate_patient_summary(patient_data)
                if not summary_text:
                    return jsonify({'success': False, 'error': 'Failed to generate AI summary'}), 500
                
                # Save AI-generated summary
                summary = PatientSummary(
                    patient_id=patient.id,
                    summary_text=summary_text,
                    summary_type='ai_generated',
                    generated_by=current_user.id
                )
                db.session.add(summary)
                db.session.commit()
                
                return jsonify({
                    'success': True, 
                    'summary_text': summary_text,
                    'message': 'AI summary generated successfully'
                })
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        elif action == 'generate_diagnosis':
            try:
                # Get the latest summary
                latest_summary = db.session.execute(
                    db.select(PatientSummary)
                    .filter_by(patient_id=patient.id)
                    .order_by(PatientSummary.created_at.desc())
                ).scalar()
                
                if not latest_summary:
                    return jsonify({'success': False, 'error': 'No summary available for diagnosis generation'}), 400
                
                diagnosis_text = AIService.generate_diagnosis_from_summary(latest_summary.summary_text)
                if not diagnosis_text:
                    return jsonify({'success': False, 'error': 'Failed to generate diagnosis from summary'}), 500
                
                # Update patient's AI diagnosis
                patient.ai_diagnosis = diagnosis_text
                patient.ai_last_updated = datetime.now(timezone.utc)
                patient.ai_assistance_enabled = True
                
                # Also update the diagnosis record if exists
                diagnosis_record = db.session.execute(
                    db.select(PatientDiagnosis).filter_by(patient_id=patient.id)
                ).scalar()
                
                if not diagnosis_record:
                    diagnosis_record = PatientDiagnosis(patient_id=patient.id)
                    db.session.add(diagnosis_record)
                
                diagnosis_record.ai_supported_diagnosis = True
                diagnosis_record.ai_alternative_diagnoses = diagnosis_text
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'diagnosis': diagnosis_text,
                    'message': 'Diagnosis generated from summary successfully'
                })
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 500
    
    # GET request - return summary data
    summaries = db.session.execute(
        db.select(PatientSummary)
        .filter_by(patient_id=patient.id)
        .order_by(PatientSummary.created_at.desc())
    ).scalars().all()
    
    summaries_data = []
    for summary in summaries:
        # Get generator username safely
        generator_name = 'Manual'
        if summary.generated_by:
            generator = db.session.get(User, summary.generated_by)
            generator_name = generator.username if generator else 'System'
        
        summaries_data.append({
            'id': summary.id,
            'summary_text': summary.summary_text,
            'summary_type': summary.summary_type,
            'created_at': summary.created_at.strftime('%Y-%m-%d %H:%M'),
            'generated_by': generator_name
        })
    
    return jsonify({
        'success': True,
        'summaries': summaries_data,
        'patient_name': patient.get_decrypted_name,
        'patient_number': patient.op_number or patient.ip_number
    })

@app.route('/doctor/patient/<int:patient_id>/summary/<int:summary_id>', methods=['DELETE'])
@login_required
def delete_patient_summary(patient_id, summary_id):
    if current_user.role not in ['doctor', 'admin']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    summary = db.session.get(PatientSummary, summary_id)
    if not summary or summary.patient_id != patient_id:
        return jsonify({'success': False, 'error': 'Summary not found'}), 404
    
    try:
        db.session.delete(summary)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Summary deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Doctor Routes - Complete with all sections
@app.route('/doctor/patient/new', methods=['GET', 'POST'])
@login_required
def doctor_new_patient():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        section = request.form.get('section')
        patient_id = request.form.get('patient_id')
        
        try:
            if section == 'biodata':
                patient_type = request.form.get('patient_type')
                patient_number = generate_patient_number(patient_type)
                
                patient = Patient(
                    op_number=patient_number if patient_type == 'OP' else None,
                    ip_number=patient_number if patient_type == 'IP' else None,
                    name=Config.encrypt_data_static(request.form.get('name')),
                    age=int(request.form.get('age')) if request.form.get('age') else None,
                    gender=request.form.get('gender'),
                    address=Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None,
                    phone=Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None,
                    destination=request.form.get('destination'),
                    occupation=Config.encrypt_data_static(request.form.get('occupation')) if request.form.get('occupation') else None,
                    religion=request.form.get('religion'),
                    nok_name=Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None,
                    nok_contact=Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None,
                    tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                    date_of_admission=datetime.strptime(request.form.get('date_of_admission'), '%Y-%m-%d').date() if request.form.get('date_of_admission') else date.today(),
                    status='active'
                )
                db.session.add(patient)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'patient_id': patient.id,
                    'next_section': 'chief_complaint'
                })

            elif section == 'chief_complaint':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                patient.chief_complaint = request.form.get('chief_complaint')
                patient.history_present_illness = request.form.get('history_present_illness')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'review_systems'
                })
                
            elif section == 'review_systems':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
                if not review:
                    review = PatientReviewSystem(patient_id=patient.id)
                    db.session.add(review)
                
                review.cns = request.form.get('cns')
                review.cvs = request.form.get('cvs')
                review.rs = request.form.get('rs')
                review.git = request.form.get('git')
                review.gut = request.form.get('gut')
                review.skin = request.form.get('skin')
                review.msk = request.form.get('msk')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'hpi'
                })

            elif section == 'hpi':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                patient.history_present_illness = request.form.get('hpi_details')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'smhx'
                })

            elif section == 'smhx':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                smhx = PatientHistory.query.filter_by(patient_id=patient.id).first()
                if not smhx:
                    smhx = PatientHistory(patient_id=patient.id)
                    db.session.add(smhx)
                
                smhx.social_history = request.form.get('social_history')
                smhx.medical_history = request.form.get('medical_history')
                smhx.surgical_history = request.form.get('surgical_history')
                smhx.family_history = request.form.get('family_history')
                smhx.allergies = request.form.get('allergies')
                smhx.medications = request.form.get('medications')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'examination'
                })

            elif section == 'examination':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                exam = PatientExamination.query.filter_by(patient_id=patient.id).first()
                if not exam:
                    exam = PatientExamination(patient_id=patient.id)
                    db.session.add(exam)
                
                exam.general_appearance = request.form.get('general_appearance')
                exam.jaundice = request.form.get('jaundice') == 'yes'
                exam.pallor = request.form.get('pallor') == 'yes'
                exam.cyanosis = request.form.get('cyanosis') == 'yes'
                exam.lymphadenopathy = request.form.get('lymphadenopathy') == 'yes'
                exam.edema = request.form.get('edema') == 'yes'
                exam.dehydration = request.form.get('dehydration') == 'yes'
                exam.dehydration_parameters = request.form.get('dehydration_parameters')
                exam.temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
                exam.pulse = int(request.form.get('pulse')) if request.form.get('pulse') else None
                exam.resp_rate = int(request.form.get('resp_rate')) if request.form.get('resp_rate') else None
                exam.bp_systolic = int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None
                exam.bp_diastolic = int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None
                exam.spo2 = int(request.form.get('spo2')) if request.form.get('spo2') else None
                exam.weight = float(request.form.get('weight')) if request.form.get('weight') else None
                exam.height = float(request.form.get('height')) if request.form.get('height') else None
                exam.bmi = float(request.form.get('bmi')) if request.form.get('bmi') else None
                exam.cvs_exam = request.form.get('cvs_exam')
                exam.resp_exam = request.form.get('resp_exam')
                exam.abdo_exam = request.form.get('abdo_exam')
                exam.cns_exam = request.form.get('cns_exam')
                exam.msk_exam = request.form.get('msk_exam')
                exam.skin_exam = request.form.get('skin_exam')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'summary'  # Now goes to summary after examination
                })

            elif section == 'summary':  # MOVED TO AFTER EXAMINATION
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                # Get the clinical summary (optional - can be empty)
                clinical_summary = request.form.get('patient_summary', '').strip()
                
                # Only save if summary is provided
                if clinical_summary:
                    summary = PatientSummary(
                        patient_id=patient.id,
                        summary_text=clinical_summary,
                        summary_type='manual',
                        generated_by=current_user.id
                    )
                    db.session.add(summary)
                    db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'diagnosis'  # Now goes to diagnosis after summary
                })

            elif section == 'diagnosis':  # NOW AFTER SUMMARY
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
                if not diagnosis:
                    diagnosis = PatientDiagnosis(patient_id=patient.id)
                    db.session.add(diagnosis)
                
                diagnosis.working_diagnosis = request.form.get('working_diagnosis')
                diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
                
                # Lab requests
                if request.form.getlist('lab_tests'):
                    for test_id in request.form.getlist('lab_tests'):
                        lab_request = LabRequest(
                            patient_id=patient.id,
                            test_id=test_id,
                            requested_by=current_user.id,
                            status='pending',
                            notes=request.form.get('lab_notes')
                        )
                        db.session.add(lab_request)
                
                # Imaging requests
                if request.form.getlist('imaging_tests'):
                    for test_id in request.form.getlist('imaging_tests'):
                        imaging_request = ImagingRequest(
                            patient_id=patient.id,
                            test_id=test_id,
                            requested_by=current_user.id,
                            status='pending',
                            notes=request.form.get('imaging_notes')
                        )
                        db.session.add(imaging_request)
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'management'
                })

            elif section == 'management':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                management = PatientManagement.query.filter_by(patient_id=patient.id).first()
                if not management:
                    management = PatientManagement(patient_id=patient.id)
                    db.session.add(management)
                
                management.treatment_plan = request.form.get('treatment_plan')
                management.follow_up = request.form.get('follow_up')
                management.notes = request.form.get('management_notes')
                
                # Prescriptions
                if request.form.getlist('drug_id'):
                    for i, drug_id in enumerate(request.form.getlist('drug_id')):
                        prescription = Prescription(
                            patient_id=patient.id,
                            drug_id=drug_id,
                            doctor_id=current_user.id,
                            dosage=request.form.getlist('dosage')[i],
                            frequency=request.form.getlist('frequency')[i],
                            duration=request.form.getlist('duration')[i],
                            quantity=request.form.getlist('quantity')[i],
                            notes=request.form.getlist('prescription_notes')[i]
                        )
                        db.session.add(prescription)
                
                # Services
                if request.form.getlist('service_id'):
                    for service_id in request.form.getlist('service_id'):
                        service_record = PatientService(
                            patient_id=patient.id,
                            service_id=service_id,
                            performed_by=current_user.id,
                            notes=request.form.get('service_notes')
                        )
                        db.session.add(service_record)
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'redirect': url_for('doctor_patient_details', patient_id=patient.id)
                })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Patient form error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    # For GET request - render the form
    lab_tests = LabTest.query.all()
    imaging_tests = ImagingTest.query.all()
    drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
    try:
        controlled_drugs = ControlledDrug.query.filter(ControlledDrug.remaining_quantity > 0).all()
    except Exception:
        controlled_drugs = []
    services = Service.query.all()
    
    return render_template('doctor/new_patient.html',
        lab_tests=lab_tests,
        imaging_tests=imaging_tests,
        drugs=drugs,
        controlled_drugs=controlled_drugs,
        services=services,
        current_date=date.today().strftime('%Y-%m-%d')
    )

# AI Assistant for diagnosis and treatment suggestions
class AIService:
    @staticmethod
    def generate_review_systems_questions(patient_data):
        """Generate review of systems questions based on patient data"""
        try:
            # Use a default model if none is specified
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Based on the following patient information, generate relevant review of systems questions:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            - Occupation: {patient_data.get('occupation', 'Not specified')}
            
            Generate 5-8 specific, targeted questions that would help in the review of systems for this patient.
            Format the response as a bulleted list.
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Review Systems Error: {str(e)}")
            return None

    @staticmethod
    def generate_hpi_questions(patient_data):
        """Generate HPI questions based on patient data"""
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Based on the following patient information, generate relevant History of Present Illness (HPI) questions:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            
            Generate 5-8 specific questions that would help elaborate the history of present illness.
            Focus on the chronology, quality, severity, and associated symptoms.
            Format the response as a bulleted list.
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI HPI Questions Error: {str(e)}")
            return None

    @staticmethod
    def generate_hpi_content(patient_data):
        """Generate HPI content based on patient data"""
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Based on the following patient information, generate a comprehensive History of Present Illness (HPI):
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            - Review of Systems: {patient_data.get('review_systems', 'Not documented')}
            
            Create a well-structured HPI that includes:
            1. Onset and chronology
            2. Quality and character
            3. Severity and progression
            4. Associated symptoms
            5. Alleviating and aggravating factors
            
            Write in professional medical narrative format.
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI HPI Generation Error: {str(e)}")
            return None

    @staticmethod
    def generate_diagnosis(patient_data):
        """Generate differential diagnosis based on patient data"""
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Based on the following patient information, generate a differential diagnosis:
            
            Patient Demographics:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            
            Clinical Presentation:
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            - History of Present Illness: {patient_data.get('history_present_illness', 'Not documented')}
            
            Review of Systems:
            {json.dumps(patient_data.get('review_systems', {}), indent=2)}
            
            Medical History:
            - Social: {patient_data.get('social_history', 'Not documented')}
            - Medical: {patient_data.get('medical_history', 'Not documented')}
            - Surgical: {patient_data.get('surgical_history', 'Not documented')}
            - Family: {patient_data.get('family_history', 'Not documented')}
            - Allergies: {patient_data.get('allergies', 'None known')}
            - Medications: {patient_data.get('medications', 'None')}
            
            Physical Examination:
            {json.dumps(patient_data.get('examination', {}), indent=2)}
            
            Please provide:
            1. Most likely diagnosis (working diagnosis)
            2. 3-5 differential diagnoses in order of likelihood
            3. Brief rationale for each
            4. Suggested diagnostic tests to confirm
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Diagnosis Error: {str(e)}")
            return None

    @staticmethod
    def analyze_lab_results(patient_data, lab_text):
        """Analyze lab results in context of patient data"""
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            prompt = f"""
            Analyze these lab results in the context of this patient:
            
            Patient Information:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            - Chief Complaint: {patient_data.get('chief_complaint', 'Not specified')}
            - Working Diagnosis: {patient_data.get('diagnosis', 'Not specified')}
            
            Lab Results:
            {lab_text}
            
            Please provide:
            1. Interpretation of abnormal values
            2. Clinical significance in context of patient
            3. Any additional tests recommended
            4. Potential treatment implications
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Lab Analysis Error: {str(e)}")
            return None

    @staticmethod
    def generate_treatment_plan(patient_data, available_drugs):
        """Generate treatment plan based on patient data and available drugs"""
        try:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            
            # Format available drugs for the prompt
            drugs_list = "\n".join([f"- {drug.name}" for drug in available_drugs])
            
            prompt = f"""
            Create a comprehensive treatment plan for this patient:
            
            Patient Information:
            - Age: {patient_data.get('age', 'Not specified')}
            - Gender: {patient_data.get('gender', 'Not specified')}
            - Diagnosis: {patient_data.get('diagnosis', 'Not specified')}
            - Allergies: {patient_data.get('allergies', 'None known')}
            - Current Medications: {patient_data.get('medications', 'None')}
            
            Available Medications:
            {drugs_list}
            
            Please provide:
            1. First-line treatment recommendations
            2. Alternative options
            3. Dosage guidelines appropriate for patient demographics
            4. Monitoring parameters
            5. Patient education points
            6. Follow-up schedule
            
            Consider drug interactions and contraindications based on patient information.
            """
            
            response = deepseek_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Treatment Plan Error: {str(e)}")
            return None

from flask import current_app
# Initialize DeepSeek client with proper error handling inside app context
with app.app_context():
    try:
        deepseek_client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
            timeout=30.0
        )
        # Test the connection
        if os.getenv("DEEPSEEK_API_KEY"):
            models = deepseek_client.models.list()
            current_app.logger.info(f"Connected to DeepSeek API. Available models: {[m.id for m in models.data]}")
        else:
            current_app.logger.warning("DEEPSEEK_API_KEY not set - AI features will be disabled")
            deepseek_client = None
    except Exception as e:
        current_app.logger.error(f"Failed to initialize DeepSeek client: {str(e)}")
        deepseek_client = None
    
@app.route('/api/verify-models', methods=['GET'])
@login_required
def verify_models():
    """Endpoint to check available models"""
    try:
        models_list = []
        
        # Test DeepSeek if configured
        if deepseek_client and os.getenv("DEEPSEEK_API_KEY"):
            deepseek_models = deepseek_client.models.list()
            models_list.extend([m.id for m in deepseek_models.data])
            current_app.logger.info(f"DeepSeek available models: {models_list}")
        
        return jsonify({
            'available_models': models_list,
            'default_model': os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/doctor/patient/ai/review_systems', methods=['POST'])
@login_required
def ai_review_systems():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.get_decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.get_decrypted_occupation or '',
            'religion': patient.religion or '',
        }
        
        questions = AIService.generate_review_systems_questions(patient_data)
        if not questions:
            return jsonify({
                'success': False,
                'error': 'Failed to generate questions'
            }), 500
            
        # Save to review systems record
        review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
        if not review:
            review = PatientReviewSystem(patient_id=patient.id)
            db.session.add(review)
        
        review.ai_suggested_questions = questions
        review.ai_last_updated = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'questions': questions
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Review systems AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500
        
@app.route('/doctor/patient/ai/hpi_questions', methods=['POST'])
@login_required
def ai_hpi_questions():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    # Updated to use SQLAlchemy 2.0 style query
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.get_decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.get_decrypted_occupation or '',
            'religion': patient.religion or '',
        }
        
        questions = AIService.generate_hpi_questions(patient_data)
        if not questions:
            return jsonify({
                'success': False,
                'error': 'Failed to generate questions'
            }), 500
            
        return jsonify({
            'success': True,
            'questions': questions
        })
        
    except Exception as e:
        current_app.logger.error(f"HPI questions AI error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/doctor/patient/ai/generate_hpi', methods=['POST'])
@login_required
def ai_generate_hpi():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    # Updated to SQLAlchemy 2.0 style query
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        # Get patient history if exists
        history = db.session.scalar(
            db.select(PatientHistory)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        # Get review systems if exists
        review = db.session.scalar(
            db.select(PatientReviewSystem)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        # Build patient data safely
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.get_decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.get_decrypted_occupation or '',
            'religion': patient.religion or '',
            'review_systems': (
                f"CNS: {review.cns or 'Not documented'}\n"
                f"CVS: {review.cvs or 'Not documented'}\n"
                f"GIT: {review.git or 'Not documented'}\n"
                f"GUT: {review.gut or 'Not documented'}\n"
                f"Skin: {review.skin or 'Not documented'}\n"
                f"MSK: {review.msk or 'Not documented'}\n"
                f"RS: {review.rs or 'Not documented'}"
            ) if review else 'Review of systems not documented'
        }
        
        hpi_content = AIService.generate_hpi_content(patient_data)
        if not hpi_content:
            return jsonify({
                'success': False,
                'error': 'Failed to generate HPI content'
            }), 500
            
        return jsonify({
            'success': True,
            'hpi_content': hpi_content
        })
        
    except Exception as e:
        current_app.logger.error(f"HPI generation AI error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
        
@app.route('/doctor/patient/ai/diagnosis', methods=['POST'])
@login_required
def ai_diagnosis():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        patient_id = request.form.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'error': 'Patient ID required'}), 400
        
        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'success': False, 'error': 'Patient not found'}), 404
        
        # Get the clinical summary from the form data
        clinical_summary = request.form.get('patient_summary', '').strip()
        
        # If no clinical summary in form, check if patient has existing summary
        if not clinical_summary:
            existing_summary = db.session.scalar(
                db.select(PatientSummary)
                .filter_by(patient_id=patient.id)
                .order_by(PatientSummary.created_at.desc())
                .limit(1)
            )
            if existing_summary:
                clinical_summary = existing_summary.summary_text
        
        if not clinical_summary:
            return jsonify({
                'success': False, 
                'error': 'Please enter a clinical summary in the summary section first'
            }), 400
        
        # Get basic patient info for context
        patient_basic_info = {
            'age': patient.age,
            'gender': patient.gender,
            'name': patient.get_decrypted_name
        }
        
        # Generate diagnosis based on clinical summary - FIXED LINE
        diagnosis = AIService.generate_diagnosis_from_summary(clinical_summary, patient_basic_info)
        if not diagnosis:
            return jsonify({
                'success': False,
                'error': 'AI service unavailable. Please try again later.'
            }), 503
            
        return jsonify({
            'success': True,
            'diagnosis': diagnosis,
            'source': 'clinical_summary'
        })
        
    except Exception as e:
        current_app.logger.error(f"Diagnosis route error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
        
@app.route('/doctor/patient/ai/analyze_lab', methods=['POST'])
@login_required
def ai_analyze_lab():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    lab_text = request.form.get('lab_text')
    
    if not patient_id or not lab_text:
        return jsonify({'success': False, 'error': 'Patient ID and lab text required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
        
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'chief_complaint': patient.chief_complaint or '',
            'diagnosis': diagnosis.working_diagnosis if diagnosis else ''
        }
        
        analysis = AIService.analyze_lab_results(patient_data, lab_text)
        if not analysis:
            return jsonify({
                'success': False,
                'error': 'Failed to analyze lab results'
            }), 500
            
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        current_app.logger.error(f"Lab analysis AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/doctor/patient/ai/treatment', methods=['POST'])
@login_required
def ai_treatment():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
        history = PatientHistory.query.filter_by(patient_id=patient.id).first()
        
        if not diagnosis or not diagnosis.working_diagnosis:
            return jsonify({'success': False, 'error': 'Diagnosis required'}), 400
        
        available_drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
        
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'diagnosis': diagnosis.working_diagnosis,
            'allergies': history.allergies if history else 'None known',
            'medications': history.medications if history else 'None'
        }
        
        treatment_plan = AIService.generate_treatment_plan(patient_data, available_drugs)
        if not treatment_plan:
            return jsonify({
                'success': False,
                'error': 'Failed to generate treatment plan'
            }), 500
            
        # Save to management record
        management = PatientManagement.query.filter_by(patient_id=patient.id).first()
        if not management:
            management = PatientManagement(patient_id=patient.id)
            db.session.add(management)
        
        management.ai_generated_plan = True
        management.ai_alternative_treatments = treatment_plan
        management.ai_last_updated = get_eat_now()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'treatment_plan': treatment_plan
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Treatment plan AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500
 
@app.errorhandler(APITimeoutError)
def handle_ai_timeout(e):
    return jsonify({
        "error": "AI service timeout",
        "message": "The AI service is taking longer than expected to respond"
    }), 504

@app.errorhandler(APIError)
def handle_ai_error(e):
    return jsonify({
        "error": "AI service error",
        "message": str(e)
    }), 502
        
@app.route('/doctor/patients/active')
@login_required
def active_patients():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patients = Patient.query.filter_by(status='active').order_by(Patient.created_at.desc()).all()
    patients_data = [{
        'id': p.id,
        'number': p.op_number or p.ip_number,
        'name': p.name,
        'age': p.age,
        'gender': p.gender,
        'date_of_admission': p.date_of_admission.strftime('%Y-%m-%d')
    } for p in patients]
    
    return jsonify(patients_data)

@app.route('/doctor/patients/old', methods=['GET', 'POST'])
@login_required
def old_patients():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    # Handle search and filtering
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Patients per page

    # Base query for completed patients
    query = Patient.query.filter_by(status='completed')

    # Apply search filter if provided
    if search_query:
        query = query.filter(
            or_(
                Patient.name.ilike(f'%{search_query}%'),
                Patient.op_number.ilike(f'%{search_query}%'),
                Patient.ip_number.ilike(f'%{search_query}%')
            )
        )

    # Get paginated results ordered by completion date (newest first)
    completed_patients = query.order_by(
        Patient.updated_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'readmit':
            patient_id = request.form.get('patient_id')
            patient = db.session.get(Patient, patient_id)
            if patient:
                try:
                    patient.status = 'active'
                    patient.updated_at = get_eat_now()
                    db.session.commit()
                    
                    log_audit('readmit_patient', 'Patient', patient.id, None, None)
                    flash(f'Patient {patient.name} readmitted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error readmitting patient: {str(e)}', 'danger')
            else:
                flash('Patient not found', 'danger')
        
        return redirect(url_for('old_patients'))

    return render_template('doctor/old_patients.html',
        patients=completed_patients,
        search_query=search_query,
        current_time=get_eat_now()
    )

@app.route('/doctor/patient/<int:patient_id>/record')
@login_required
def patient_medical_record(patient_id):
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('doctor_patients'))
    
    # Get all medical record components
    review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
    history = PatientHistory.query.filter_by(patient_id=patient.id).first()
    examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
    diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
    management = PatientManagement.query.filter_by(patient_id=patient.id).first()
    
    # Get all related records
    lab_requests = LabRequest.query.filter_by(patient_id=patient.id).order_by(LabRequest.created_at.desc()).all()
    imaging_requests = ImagingRequest.query.filter_by(patient_id=patient.id).order_by(ImagingRequest.created_at.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).options(db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug)).order_by(Prescription.created_at.desc()).all()
    services = PatientService.query.filter_by(patient_id=patient.id).order_by(PatientService.created_at.desc()).all()
    
    return render_template('doctor/medical_record.html',
        patient=patient,
        review_systems=review_systems,
        history=history,
        examination=examination,
        diagnosis=diagnosis,
        management=management,
        lab_requests=lab_requests,
        imaging_requests=imaging_requests,
        prescriptions=prescriptions,
        services=services
    )

@app.route('/doctor/patient/<int:patient_id>/complete', methods=['POST'])
@login_required
def complete_patient_treatment(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
        
    try:
        patient.status = 'completed'
        patient.updated_at = get_eat_now()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/doctor/patient/<int:patient_id>', methods=['DELETE'])
@login_required
def delete_patient(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
        
    try:
        db.session.delete(patient)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/doctor/patient/readmit', methods=['POST'])
@login_required
def readmit_patient():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    patient = db.session.get(Patient, patient_id)
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    try:
        patient.status = 'active'
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/doctor/patient/new', methods=['POST'])
@login_required
def handle_patient_sections():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    section = request.form.get('section')
    patient_id = request.form.get('patient_id')

    try:
        if section == 'biodata':
            patient_type = request.form.get('patient_type')
            patient_number = generate_patient_number(patient_type)
            
            patient = Patient(
                op_number=patient_number if patient_type == 'OP' else None,
                ip_number=patient_number if patient_type == 'IP' else None,
                name=request.form.get('name'),
                age=int(request.form.get('age')) if request.form.get('age') else None,
                gender=request.form.get('gender'),
                address=request.form.get('address') if request.form.get('address') else None,
                phone=request.form.get('phone') if request.form.get('phone') else None,
                destination=request.form.get('destination'),
                occupation=request.form.get('occupation') if request.form.get('occupation') else None,
                religion=request.form.get('religion'),
                nok_name=request.form.get('nok_name') if request.form.get('nok_name') else None,
                nok_contact=request.form.get('nok_contact') if request.form.get('nok_contact') else None,
                tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                date_of_admission=datetime.strptime(request.form.get('date_of_admission'), '%Y-%m-%d').date() if request.form.get('date_of_admission') else date.today(),
                status='active'
            )
            db.session.add(patient)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'patient_id': patient.id,
                'next_section': 'chief_complaint'
            })

        elif section == 'chief_complaint':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            patient.chief_complaint = request.form.get('chief_complaint')
            patient.history_present_illness = request.form.get('history_present_illness')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'review_systems'
            })

        elif section == 'review_systems':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
            if not review:
                review = PatientReviewSystem(patient_id=patient.id)
                db.session.add(review)
            
            review.cns = request.form.get('cns')
            review.cvs = request.form.get('cvs')
            review.rs = request.form.get('rs')
            review.git = request.form.get('git')
            review.gut = request.form.get('gut')
            review.skin = request.form.get('skin')
            review.msk = request.form.get('msk')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'hpi'
            })

        elif section == 'hpi':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            patient.history_present_illness = request.form.get('hpi_details')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'smhx'
            })

        elif section == 'smhx':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            smhx = PatientHistory.query.filter_by(patient_id=patient.id).first()
            if not smhx:
                smhx = PatientHistory(patient_id=patient.id)
                db.session.add(smhx)
            
            smhx.social_history = request.form.get('social_history')
            smhx.medical_history = request.form.get('medical_history')
            smhx.surgical_history = request.form.get('surgical_history')
            smhx.family_history = request.form.get('family_history')
            smhx.allergies = request.form.get('allergies')
            smhx.medications = request.form.get('medications')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'examination'
            })

        elif section == 'examination':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            exam = PatientExamination.query.filter_by(patient_id=patient.id).first()
            if not exam:
                exam = PatientExamination(patient_id=patient.id)
                db.session.add(exam)
            
            exam.general_appearance = request.form.get('general_appearance')
            exam.jaundice = request.form.get('jaundice') == 'yes'
            exam.pallor = request.form.get('pallor') == 'yes'
            exam.cyanosis = request.form.get('cyanosis') == 'yes'
            exam.lymphadenopathy = request.form.get('lymphadenopathy') == 'yes'
            exam.edema = request.form.get('edema') == 'yes'
            exam.dehydration = request.form.get('dehydration') == 'yes'
            exam.dehydration_parameters = request.form.get('dehydration_parameters')
            exam.temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
            exam.pulse = int(request.form.get('pulse')) if request.form.get('pulse') else None
            exam.resp_rate = int(request.form.get('resp_rate')) if request.form.get('resp_rate') else None
            exam.bp_systolic = int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None
            exam.bp_diastolic = int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None
            exam.spo2 = int(request.form.get('spo2')) if request.form.get('spo2') else None
            exam.weight = float(request.form.get('weight')) if request.form.get('weight') else None
            exam.height = float(request.form.get('height')) if request.form.get('height') else None
            exam.bmi = float(request.form.get('bmi')) if request.form.get('bmi') else None
            exam.cvs_exam = request.form.get('cvs_exam')
            exam.resp_exam = request.form.get('resp_exam')
            exam.abdo_exam = request.form.get('abdo_exam')
            exam.cns_exam = request.form.get('cns_exam')
            exam.msk_exam = request.form.get('msk_exam')
            exam.skin_exam = request.form.get('skin_exam')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'diagnosis'
            })

        elif section == 'diagnosis':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
            if not diagnosis:
                diagnosis = PatientDiagnosis(patient_id=patient.id)
                db.session.add(diagnosis)
            
            diagnosis.working_diagnosis = request.form.get('working_diagnosis')
            diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
            
            # Lab requests
            if request.form.getlist('lab_tests'):
                for test_id in request.form.getlist('lab_tests'):
                    lab_request = LabRequest(
                        patient_id=patient.id,
                        test_id=test_id,
                        requested_by=current_user.id,
                        status='pending',
                        notes=request.form.get('lab_notes')
                    )
                    db.session.add(lab_request)
            
            # Imaging requests
            if request.form.getlist('imaging_tests'):
                for test_id in request.form.getlist('imaging_tests'):
                    imaging_request = ImagingRequest(
                        patient_id=patient.id,
                        test_id=test_id,
                        requested_by=current_user.id,
                        status='pending',
                        notes=request.form.get('imaging_notes')
                    )
                    db.session.add(imaging_request)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'management'
            })

        elif section == 'management':
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            management = PatientManagement.query.filter_by(patient_id=patient.id).first()
            if not management:
                management = PatientManagement(patient_id=patient.id)
                db.session.add(management)
            
            management.treatment_plan = request.form.get('treatment_plan')
            management.follow_up = request.form.get('follow_up')
            management.notes = request.form.get('management_notes')
            
            # Prescriptions
            if request.form.getlist('drug_id'):
                for i, drug_id in enumerate(request.form.getlist('drug_id')):
                    prescription = Prescription(
                        patient_id=patient.id,
                        drug_id=drug_id,
                        doctor_id=current_user.id,
                        dosage=request.form.getlist('dosage')[i],
                        frequency=request.form.getlist('frequency')[i],
                        duration=request.form.getlist('duration')[i],
                        quantity=request.form.getlist('quantity')[i],
                        notes=request.form.getlist('prescription_notes')[i]
                    )
                    db.session.add(prescription)
            
            # Services
            if request.form.getlist('service_id'):
                for service_id in request.form.getlist('service_id'):
                    service_record = PatientService(
                        patient_id=patient.id,
                        service_id=service_id,
                        performed_by=current_user.id,
                        notes=request.form.get('service_notes')
                    )
                    db.session.add(service_record)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'redirect': url_for('doctor_patient_details', patient_id=patient.id)
            })

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/doctor/patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def doctor_patient_details(patient_id):
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('doctor_patients'))
    
    drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
    services = Service.query.all()
    
    if request.method == 'POST':
        section = request.form.get('section')
        
        # Add these new sections for chief complaint and HPI
        if section == 'chief_complaint':
            try:
                chief_complaint = request.form.get('chief_complaint')
                if chief_complaint:
                    patient.chief_complaint = chief_complaint
                    db.session.commit()
                    flash('Chief complaint updated successfully!', 'success')
                else:
                    flash('Chief complaint cannot be empty', 'warning')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating chief complaint: {str(e)}', 'danger')
        
        elif section == 'hpi':
            try:
                hpi = request.form.get('history_present_illness')
                if hpi:
                    patient.history_present_illness = hpi
                    db.session.commit()
                    flash('History of present illness updated successfully!', 'success')
                else:
                    flash('History of present illness cannot be empty', 'warning')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating history of present illness: {str(e)}', 'danger')
        
        elif section == 'review_systems':
            try:
                review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
                if not review_systems:
                    review_systems = PatientReviewSystem(patient_id=patient.id)
                    db.session.add(review_systems)
                
                review_systems.cns = request.form.get('cns')
                review_systems.cvs = request.form.get('cvs')
                review_systems.rs = request.form.get('rs')
                review_systems.git = request.form.get('git')
                review_systems.gut = request.form.get('gut')
                review_systems.msk = request.form.get('msk')
                
                db.session.commit()
                flash('Review of systems updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating review of systems: {str(e)}', 'danger')
        
        elif section == 'history':
            try:
                history = PatientHistory.query.filter_by(patient_id=patient.id).first()
                if not history:
                    history = PatientHistory(patient_id=patient.id)
                    db.session.add(history)
                
                history.medical_history = request.form.get('medical_history')
                history.surgical_history = request.form.get('surgical_history')
                history.family_history = request.form.get('family_history')
                history.allergies = request.form.get('allergies')
                
                db.session.commit()
                flash('Medical history updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating medical history: {str(e)}', 'danger')
        
        elif section == 'examination':
            try:
                examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
                if not examination:
                    examination = PatientExamination(patient_id=patient.id)
                    db.session.add(examination)
                
                examination.general_appearance = request.form.get('general_appearance')
                examination.temperature = request.form.get('temperature')
                examination.pulse = request.form.get('pulse')
                examination.resp_rate = request.form.get('resp_rate')
                examination.bp_systolic = request.form.get('bp_systolic')
                examination.bp_diastolic = request.form.get('bp_diastolic')
                examination.spo2 = request.form.get('spo2')
                examination.cvs_exam = request.form.get('cvs_exam')
                examination.resp_exam = request.form.get('resp_exam')
                examination.abdo_exam = request.form.get('abdo_exam')
                examination.cns_exam = request.form.get('cns_exam')
                
                db.session.commit()
                flash('Examination findings updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating examination findings: {str(e)}', 'danger')
        
        elif section == 'diagnosis':
            try:
                diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
                if not diagnosis:
                    diagnosis = PatientDiagnosis(patient_id=patient.id)
                    db.session.add(diagnosis)
                
                diagnosis.working_diagnosis = request.form.get('working_diagnosis')
                diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
                
                db.session.commit()
                flash('Diagnosis updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating diagnosis: {str(e)}', 'danger')
        
        elif section == 'management':
            try:
                # Update or create management plan
                management = PatientManagement.query.filter_by(patient_id=patient.id).first()
                if not management:
                    management = PatientManagement(patient_id=patient.id)
                    db.session.add(management)
                
                management.treatment_plan = request.form.get('treatment_plan', '')
                management.follow_up = request.form.get('follow_up', '')
                management.notes = request.form.get('management_notes', '')
                
                # Handle prescriptions
                drug_ids = request.form.getlist('drug_id')
                quantities = request.form.getlist('quantity')
                dosages = request.form.getlist('dosage')
                frequencies = request.form.getlist('frequency')
                durations = request.form.getlist('duration')
                prescription_notes = request.form.getlist('prescription_notes')
                
                # Only create prescription if there are drugs specified
                if any(drug_ids):
                    prescription = Prescription(
                        patient_id=patient.id,
                        doctor_id=current_user.id,
                        notes="Prescription from management plan",
                        status='pending'
                    )
                    db.session.add(prescription)
                    db.session.flush()  # Get the prescription ID
                    
                    for i in range(len(drug_ids)):
                        if drug_ids[i] and quantities[i]:
                            drug = db.session.get(Drug, drug_ids[i])
                            if drug:
                                prescription_item = PrescriptionItem(
                                    prescription_id=prescription.id,
                                    drug_id=drug.id,
                                    quantity=int(quantities[i]),
                                    dosage=dosages[i],
                                    frequency=frequencies[i],
                                    duration=durations[i],
                                    notes=prescription_notes[i] if i < len(prescription_notes) else None,
                                    status='pending'
                                )
                                db.session.add(prescription_item)
                                # Update drug stock
                                drug.remaining_quantity -= int(quantities[i])
                
                # Handle services
                service_ids = request.form.getlist('service_id')
                service_notes = request.form.get('service_notes', '')
                
                for service_id in service_ids:
                    if service_id:
                        service = db.session.get(Service, service_id)
                        if service:
                            patient_service = PatientService(
                                patient_id=patient.id,
                                service_id=service.id,
                                notes=service_notes,
                                requested_by=current_user.id
                            )
                            db.session.add(patient_service)
                
                db.session.commit()
                flash('Management plan updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating management plan: {str(e)}', 'danger')
        
        elif section == 'lab_request':
            try:
                test_id = request.form.get('test_id')
                if not test_id:
                    flash('Please select a test', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                lab_test = db.session.get(LabTest, test_id)
                if not lab_test:
                    flash('Lab test not found', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                lab_request = LabRequest(
                    patient_id=patient.id,
                    test_id=lab_test.id,
                    status='pending',
                    notes=request.form.get('notes'),
                    requested_by=current_user.id
                )
                db.session.add(lab_request)
                db.session.commit()
                
                flash('Lab request sent successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sending lab request: {str(e)}', 'danger')
        
        elif section == 'imaging_request':
            try:
                test_id = request.form.get('test_id')
                if not test_id:
                    flash('Please select a test', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                imaging_test = db.session.get(ImagingTest, test_id)
                if not imaging_test:
                    flash('Imaging test not found', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                imaging_request = ImagingRequest(
                    patient_id=patient.id,
                    test_id=imaging_test.id,
                    status='pending',
                    notes=request.form.get('notes'),
                    requested_by=current_user.id
                )
                db.session.add(imaging_request)
                db.session.commit()
                
                flash('Imaging request sent successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sending imaging request: {str(e)}', 'danger')
        
        elif request.form.get('action') == 'complete_treatment':
            try:
                patient.status = 'completed'
                patient.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                flash('Patient treatment marked as completed!', 'success')
                return redirect(url_for('doctor_patients'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error completing treatment: {str(e)}', 'danger')
        
        elif request.form.get('action') == 'readmit_patient':
            try:
                patient.status = 'active'
                patient.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                flash('Patient readmitted successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error readmitting patient: {str(e)}', 'danger')
        
        return redirect(url_for('doctor_patient_details', patient_id=patient_id))
    
    # Get all related data
    review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
    history = PatientHistory.query.filter_by(patient_id=patient.id).first()
    examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
    diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
    management = PatientManagement.query.filter_by(patient_id=patient.id).first()
    lab_tests = LabTest.query.all()
    imaging_tests = ImagingTest.query.all()
    lab_requests = LabRequest.query.filter_by(patient_id=patient.id).all()
    imaging_requests = ImagingRequest.query.filter_by(patient_id=patient.id).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).options(db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug)).all()
    patient_services = PatientService.query.filter_by(patient_id=patient.id).all()
    
    return render_template('doctor/patient_details.html',
        patient=patient,
        review_systems=review_systems,
        history=history,
        examination=examination,
        diagnosis=diagnosis,
        management=management,
        lab_tests=lab_tests,
        imaging_tests=imaging_tests,
        lab_requests=lab_requests,
        imaging_requests=imaging_requests,
        prescriptions=prescriptions,
        patient_services=patient_services,
        drugs=drugs,
        services=services
    )

@app.route('/doctor/prescription/<int:prescription_id>')
@login_required
def doctor_prescription_details(prescription_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    prescription = db.session.get(Prescription, prescription_id)
    if not prescription:
        return jsonify({'error': 'Prescription not found'}), 404
    
    items = [{
        'id': item.id,
        'drug_id': item.drug_id,
        'drug_name': item.drug.name,
        'quantity': item.quantity,
        'dosage': item.dosage,
        'frequency': item.frequency,
        'duration': item.duration,
        'notes': item.notes,
        'status': item.status
    } for item in prescription.items]
    
    return jsonify({
        'id': prescription.id,
        'patient_id': prescription.patient_id,
        'patient_name': prescription.patient.name if prescription.patient else '',
        'patient_number': prescription.patient.op_number or prescription.patient.ip_number if prescription.patient else '',
        'notes': prescription.notes,
        'status': prescription.status,
        'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
        'items': items
    })

@app.route('/doctor/patient/complete_prescription', methods=['POST'])
@login_required
def complete_prescription():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    patient_id = data.get('patient_id')
    prescriptions = data.get('prescriptions', [])
    
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    if not prescriptions:
        return jsonify({'success': False, 'error': 'No prescriptions provided'}), 400
    
    try:
        normal_items = []
        controlled_items = []
        for item in prescriptions:
            is_controlled = bool(item.get('is_controlled')) or bool(item.get('controlled_drug_id'))
            if is_controlled:
                controlled_items.append(item)
            else:
                normal_items.append(item)

        created_prescription_id = None
        created_controlled_prescription_id = None

        if normal_items:
            prescription = Prescription(
                patient_id=patient_id,
                doctor_id=current_user.id,
                status='pending',
                notes='Prescription completed by doctor'
            )
            db.session.add(prescription)
            db.session.flush()

            for item in normal_items:
                drug = db.session.get(Drug, item.get('drug_id'))
                if not drug:
                    continue
                db.session.add(PrescriptionItem(
                    prescription_id=prescription.id,
                    drug_id=drug.id,
                    quantity=int(item['quantity']),
                    dosage=item.get('dosage'),
                    frequency=item.get('frequency'),
                    duration=item.get('duration'),
                    notes=item.get('notes'),
                    status='pending'
                ))

            created_prescription_id = prescription.id
            log_audit('create_prescription', 'Prescription', prescription.id, None, {
                'patient_id': patient_id,
                'items_count': len(normal_items),
                'action': 'doctor_completed_prescription'
            })

        if controlled_items:
            c_prescription = ControlledPrescription(
                patient_id=patient_id,
                doctor_id=current_user.id,
                status='pending',
                notes='Controlled prescription completed by doctor'
            )
            db.session.add(c_prescription)
            db.session.flush()

            for item in controlled_items:
                cdrug = db.session.get(ControlledDrug, item.get('controlled_drug_id'))
                if not cdrug:
                    continue
                db.session.add(ControlledPrescriptionItem(
                    controlled_prescription_id=c_prescription.id,
                    controlled_drug_id=cdrug.id,
                    quantity=int(item['quantity']),
                    dosage=item.get('dosage'),
                    frequency=item.get('frequency'),
                    duration=item.get('duration'),
                    notes=item.get('notes'),
                    status='pending'
                ))

            created_controlled_prescription_id = c_prescription.id
            log_audit('create_controlled_prescription', 'ControlledPrescription', c_prescription.id, None, {
                'patient_id': patient_id,
                'items_count': len(controlled_items),
                'action': 'doctor_completed_controlled_prescription'
            })

        db.session.commit()

        return jsonify({
            'success': True,
            'prescription_id': created_prescription_id,
            'controlled_prescription_id': created_controlled_prescription_id,
            'message': 'Prescription sent to pharmacy successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
# Receptionist Routes
@app.route('/receptionist')
@login_required
def receptionist_dashboard():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Calculate today's patients
    today_patients = Patient.query.filter(
        func.date(Sale.created_at) == date.today()
    ).count()
    
    # Calculate active patients
    active_patients = Patient.query.filter_by(status='active').count()
    
    # Calculate today's sales
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        func.date(Sale.created_at) == date.today()
    ).scalar() or 0
    
    # Calculate outstanding bills (from Debtor model)
    outstanding_bills = db.session.query(func.sum(Debtor.amount_owed)).scalar() or 0
    
    # Get today's appointments (placeholder - you'll need to implement this)
    today_appointments = Appointment.query.filter(
        Appointment.date == date.today()
    ).count()

    pending_appointments = Appointment.query.filter(
        Appointment.status == 'scheduled'
    ).count()

    appointments = Appointment.query.filter(
        Appointment.date == date.today()
    ).order_by(Appointment.time).all()
        
    return render_template('receptionist/dashboard.html',
        today_patients=today_patients,
        active_patients=active_patients,
        today_sales=today_sales,
        outstanding_bills=outstanding_bills,
        today_appointments=today_appointments,
        pending_appointments=pending_appointments,
        appointments=appointments
    )


@app.route('/receptionist/patients')
@login_required
def receptionist_patients():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return render_template('receptionist/patients.html', patients=patients)

@app.route('/receptionist/patient/<int:patient_id>')
@login_required
def receptionist_patient_details(patient_id):
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patient = Patient.query.get(patient_id)
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('receptionist_patients'))
    
    services = Service.query.all()
    lab_tests = LabTest.query.all()
    patient_labs = patient.labs
    prescriptions = patient.prescriptions
    
    # Calculate totals
    lab_total = sum(lab.test.price for lab in patient_labs)
    service_total = 0  # Will be calculated from selected services
    prescription_total = sum(
        item.drug.selling_price * item.quantity 
        for prescription in prescriptions 
        for item in prescription.items 
        if item.status == 'dispensed'
    )
    
    return render_template('receptionist/patient_details.html',
        patient=patient,
        services=services,
        lab_tests=lab_tests,
        patient_labs=patient_labs,
        prescriptions=prescriptions,
        lab_total=lab_total,
        service_total=service_total,
        prescription_total=prescription_total
    )

@app.route('/receptionist/billing', methods=['POST'])
@login_required
def create_bill():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    data = request.get_json()
    patient_id = data.get('patient_id')
    service_ids = data.get('services', [])
    lab_ids = data.get('labs', [])
    
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    try:
        # Create sale
        sale = Sale(
            sale_number=generate_sale_number(),
            patient_id=patient.id,
            user_id=current_user.id,
            total_amount=0,  # Will be calculated
            payment_method=data.get('payment_method', 'cash'),
            status='completed'
        )
        db.session.add(sale)
        db.session.flush()  # To get the sale ID
        
        total_amount = 0
        
        # Add services
        for service_id in service_ids:
            service = Service.query.get(service_id)
            if service:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    service_id=service.id,
                    description=service.name,
                    quantity=1,
                    unit_price=service.price,
                    total_price=service.price
                )
                db.session.add(sale_item)
                total_amount += service.price
        
        # Add lab tests
        for lab_id in lab_ids:
            lab = LabTest.query.get(lab_id)
            if lab:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    lab_test_id=lab.id,
                    description=lab.name,
                    quantity=1,
                    unit_price=lab.price,
                    total_price=lab.price
                )
                db.session.add(sale_item)
                total_amount += lab.price
        
        # Add dispensed prescriptions
        prescriptions = Prescription.query.filter_by(patient_id=patient.id, status='dispensed').all()
        for prescription in prescriptions:
            for item in prescription.items:
                if item.status == 'dispensed' and item.drug:
                    sale_item = SaleItem(
                        sale_id=sale.id,
                        drug_id=item.drug.id,
                        description=f"{item.drug.name} - {item.dosage}",
                        quantity=item.quantity,
                        unit_price=item.drug.selling_price,
                        total_price=item.drug.selling_price * item.quantity
                    )
                    db.session.add(sale_item)
                    total_amount += item.drug.selling_price * item.quantity
        
        # Update sale total
        sale.total_amount = total_amount
        
        # Create transaction
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='sale',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=sale.id
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        log_audit('create_bill', 'Sale', sale.id, None, {
            'patient_id': patient.id,
            'total_amount': total_amount
        })
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/receptionist/sale/<int:sale_id>/receipt')
@login_required
def receptionist_receipt(sale_id):
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    sale = Sale.query.get(sale_id)
    if not sale:
        flash('Sale not found', 'danger')
        return redirect(url_for('receptionist_dashboard'))
    
    return render_template('receptionist/receipt.html', sale=sale)

# API Routes
@app.route('/api/drugs')
@login_required
def api_drugs():
    if current_user.role == 'admin':
        filter_type = request.args.get('filter', 'all')
        
        query = db.session.query(Drug)
        
        if filter_type == 'low_stock':
            query = query.filter(Drug.remaining_quantity < 5, Drug.remaining_quantity > 0)
        elif filter_type == 'expiring_soon':
            # Drugs expiring in the next 30 days
            thirty_days_later = date.today() + timedelta(days=30)
            query = query.filter(Drug.expiry_date <= thirty_days_later, Drug.expiry_date >= date.today())
        elif filter_type == 'out_of_stock':
            query = query.filter(Drug.remaining_quantity <= 0)
        elif filter_type == 'expired':
            # Only expired drugs
            today = datetime.now().date()
            query = query.filter(Drug.expiry_date < today)
        
        drugs = query.order_by(Drug.name).all()
        
        drugs_data = [{
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'buying_price': float(drug.buying_price),
            'selling_price': float(drug.selling_price),
            'stocked_quantity': drug.stocked_quantity,
            'sold_quantity': drug.sold_quantity,
            'remaining_quantity': drug.remaining_quantity,
            'expiry_date': drug.expiry_date.isoformat() if drug.expiry_date else None,
            'status': get_drug_status(drug)  # Helper function to determine status
        } for drug in drugs]
        
        return jsonify(drugs_data)
    else:
        # Other roles get limited drug details
        search = request.args.get('search', '')
        limit = request.args.get('limit', 10, type=int)
        
        query = Drug.query.filter(Drug.remaining_quantity > 0)
        if search:
            query = query.filter(Drug.name.ilike(f'%{search}%'))
        
        drugs = query.limit(limit).all()
        
        return jsonify([{
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'selling_price': float(drug.selling_price),
            'remaining_quantity': drug.remaining_quantity
        } for drug in drugs])

# Helper function to determine drug status
def get_drug_status(drug):
    remaining = drug.remaining_quantity
    expiry_date = drug.expiry_date
    today = datetime.now().date()
    
    if remaining <= 0:
        return 'Out of Stock'
    elif remaining < 5:
        return 'Low Stock'
    elif expiry_date and expiry_date < today:
        return 'Expired'
    elif expiry_date and (expiry_date - today).days < 30:
        return 'Expiring Soon'
    else:
        return 'In Stock'

# Add this function to generate drug numbers automatically
def generate_drug_number():
    last_drug = Drug.query.order_by(Drug.id.desc()).first()
    if last_drug:
        last_number = int(last_drug.drug_number.split('-')[-1]) if '-' in last_drug.drug_number else 0
        new_number = last_number + 1
    else:
        new_number = 1
    return f"DRG-{new_number:04d}"


def generate_controlled_drug_number():
    last_drug = ControlledDrug.query.order_by(ControlledDrug.id.desc()).first()
    if last_drug and last_drug.controlled_drug_number and '-' in last_drug.controlled_drug_number:
        try:
            last_number = int(last_drug.controlled_drug_number.split('-')[-1])
        except Exception:
            last_number = 0
    else:
        last_number = 0
    new_number = last_number + 1
    return f"CDR-{new_number:04d}"


def generate_controlled_sale_number():
    return f"CSALE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"


def _allowed_prescription_file(filename: str) -> bool:
    if not filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in {'jpg', 'jpeg', 'png', 'webp', 'pdf'}


def _save_prescription_sheet(file_storage):
    """Save uploaded prescription sheet to uploads/controlled_prescriptions and return relative path."""
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None
    if not _allowed_prescription_file(file_storage.filename):
        raise ValueError('Unsupported file type. Use jpg, png, webp, or pdf.')

    filename = secure_filename(file_storage.filename)
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique = f"{stamp}_{random.randint(1000, 9999)}_{filename}"

    upload_dir = os.path.join(app.root_path, 'uploads', 'controlled_prescriptions')
    os.makedirs(upload_dir, exist_ok=True)
    full_path = os.path.join(upload_dir, unique)
    file_storage.save(full_path)
    return os.path.join('uploads', 'controlled_prescriptions', unique).replace('\\', '/')

@app.route('/api/drugs/<int:drug_id>')
@login_required
def api_single_drug(drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    return jsonify({
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name,
        'specification': drug.specification,
        'buying_price': float(drug.buying_price),
        'selling_price': float(drug.selling_price),
        'stocked_quantity': drug.stocked_quantity,
        'expiry_date': drug.expiry_date.isoformat()
    })

@app.route('/api/drugs/stats')
@login_required
def api_drug_stats():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    total_value = db.session.query(func.sum(Drug.selling_price * (Drug.stocked_quantity - Drug.sold_quantity))).scalar() or 0
    low_stock = db.session.query(func.count(Drug.id)).filter(Drug.stocked_quantity - Drug.sold_quantity < 10).filter(Drug.stocked_quantity - Drug.sold_quantity > 0).scalar()
    expiring_soon = db.session.query(func.count(Drug.id)).filter(Drug.expiry_date <= date.today() + timedelta(days=30)).filter(Drug.expiry_date >= date.today()).scalar()
    out_of_stock = db.session.query(func.count(Drug.id)).filter(Drug.stocked_quantity - Drug.sold_quantity <= 0).scalar()
    
    return jsonify({
        'total_value': float(total_value),
        'low_stock': low_stock,
        'expiring_soon': expiring_soon,
        'out_of_stock': out_of_stock
    })

@app.route('/api/patients')
@login_required
def api_patients():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = Patient.query
    if search:
        query = query.filter(
            (Patient.op_number.ilike(f'%{search}%')) |
            (Patient.ip_number.ilike(f'%{search}%')) |
            (Patient.name.ilike(f'%{search}%'))
        )
    
    patients = query.limit(limit).all()
    
    return jsonify([{
        'id': patient.id,
        'op_number': patient.op_number,
        'ip_number': patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender
    } for patient in patients])

@app.route('/receptionist/billing')
@login_required
def receptionist_billing():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patients = Patient.query.filter_by(status='active').all()
    services = Service.query.all()
    lab_tests = LabTest.query.all()
    
    return render_template('receptionist/billing.html',
        patients=patients,
        services=services,
        lab_tests=lab_tests
    )

@app.route('/api/lab-tests')
@login_required
def api_lab_tests():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = LabTest.query
    if search:
        query = query.filter(LabTest.name.ilike(f'%{search}%'))
    
    tests = query.limit(limit).all()
    
    return jsonify([{
        'id': test.id,
        'name': test.name,
        'price': test.price,
        'description': test.description
    } for test in tests])

@app.route('/api/services')
@login_required
def api_services():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = Service.query
    if search:
        query = query.filter(Service.name.ilike(f'%{search}%'))
    
    services = query.limit(limit).all()
    
    return jsonify([{
        'id': service.id,
        'name': service.name,
        'price': service.price,
        'description': service.description
    } for service in services])

@app.route('/static/js/sw.js')
def sw():
    return send_from_directory('static/js', 'sw.js')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')


# Error handlers
@app.errorhandler(400)
def bad_request(e):
    return render_template('errors/400.html'), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template('errors/401.html'), 401

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('errors/405.html'), 405

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500


def initialize_database():
    with app.app_context():
        # Create all database tables
        db.create_all()

app.register_blueprint(auth_bp, url_prefix='/auth')

if __name__ == '__main__':
    # Create necessary directories
    if not os.path.exists('instance'):
        os.makedirs('instance')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['BACKUP_FOLDER']):
        os.makedirs(app.config['BACKUP_FOLDER'])

    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    if os.environ.get('RENDER'):
        # Production - use gunicorn or platform-provided process manager
        app.logger.info("Production mode - ready for gunicorn")
    else:
        # Development - start Flask dev server
        app.logger.info("Development mode - starting Flask server")
        try:
            initialize_data()
        except Exception:
            app.logger.exception('initialize_data failed, continuing to start server')

        host = '0.0.0.0'
        port = int(os.environ.get('PORT', 5000))

        app.logger.info(f"Starting server on {host}:{port} (DEBUG={app.config.get('DEBUG', False)})")
        print(f"Starting server on {host}:{port} (DEBUG={app.config.get('DEBUG', False)})")
        app.run(host=host, port=port, debug=app.config.get('DEBUG', False))